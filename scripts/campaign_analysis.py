"""Fit development-only surrogates, allocate bounded adaptive/FE designs, publish audit reports."""
import json
import os
import tarfile
import tempfile
from pathlib import Path

import joblib
from campaign_controller import CANONICAL, persist

from honeycomb_studio.campaign_acceptance import confirmation_report
from honeycomb_studio.campaign_export import export_campaign
from honeycomb_studio.campaign_ml import (
    adaptive_designs,
    confirmation_designs,
    evaluate_locked_test,
    fit_surrogates,
    pareto_diagnostics,
    rear_failure_model,
)
from honeycomb_studio.campaign_queue import CampaignStore
from honeycomb_studio.cloud_archive import ReleaseArchive
from honeycomb_studio.cloud_github import CampaignApp
from honeycomb_studio.models import digest


def main():
    app = CampaignApp()
    github = app.repository(CANONICAL)
    store = CampaignStore(github)
    manifest = store.load(os.environ.get('CORE_DAMAGE_CAMPAIGN_ID', 'core-damage-v2-20261106'))
    if manifest.get('phase') != 'analysis_pending' or manifest.get('analysis_ticket') != os.environ['ANALYSIS_TICKET']:
        raise ValueError('This analysis ticket is stale or already consumed')
    phase = manifest['analysis_origin_phase']
    manifest['phase'] = phase
    role = 'confirmation' if phase == 'confirmation' else 'adaptive' if phase == 'adaptive' else 'development'
    rows = [r for r in manifest['designs'] if r['role'] == role]
    if phase not in ('production', 'adaptive', 'confirmation') or not rows or any(r['status'] != 'completed' for r in rows):
        raise ValueError('Development phase is incomplete; do not train on partial responses')
    fitted = None
    if phase == 'confirmation':
        report = confirmation_report(manifest)
        manifest.update(final_fe_report=report, phase='completed' if report['passed'] else 'verification_failed')
    else:
        fitted, report = fit_surrogates(manifest)
        classifier, failure_report = rear_failure_model(manifest)
        stability = pareto_diagnostics(manifest, fitted[report['winner']], manifest.get('pareto_diagnostics'))
        manifest.update(pareto_diagnostics=stability, failure_report=failure_report)
        allocated = sum(r['role'] == 'adaptive' for r in manifest['designs'])
        if allocated + 20 <= min(80, manifest.get('max_adaptive', 80)) and (not report['passed'] or not stability['passed']):
            manifest['designs'].extend(adaptive_designs(manifest, fitted))
            manifest.update(phase='adaptive', initial_cv_report=report)
        elif not report['passed'] or not stability['passed']:
            manifest.update(phase='insufficient_data', cv_report=report,
                            error='Adaptive budget exhausted without meeting development/Pareto acceptance')
        else:
            manifest.update(model_locked=True, locked_model_report=report,
                            locked_training_hash=digest(report['training_ids']))
            # Test failure is reported; it cannot trigger test-guided re-fitting.
            test_report = evaluate_locked_test(manifest, fitted[report['winner']], report)
            candidates = confirmation_designs(manifest, fitted[report['winner']], classifier)
            for candidate in candidates:
                prediction = fitted[report['winner']].predict([[candidate['model'][k] for k in manifest['bounds']]])[0]
                candidate['surrogate_prediction'] = dict(zip(report['targets'], map(float, prediction), strict=True))
            manifest['designs'].extend(candidates)
            manifest.update(phase='confirmation', locked_test_report=test_report)
    with tempfile.TemporaryDirectory(prefix='campaign-analysis-') as temp:
        directory = Path(temp)
        export_campaign(manifest, directory)
        (directory / ('fe-confirmation.json' if phase == 'confirmation' else 'cross-validation.json')).write_text(
            json.dumps(report, indent=2), encoding='utf-8')
        # joblib contains only models fitted in this process; loading arbitrary uploaded pickle is forbidden.
        if fitted is not None:
            joblib.dump({'regressors': fitted, 'rear_classifier': classifier, 'report': report}, directory / 'surrogates.joblib')
        # Keep model bytes in a content-hashed archive using the normal checksum publication mechanism.
            with tarfile.open(directory / 'state.tar', 'w') as archive:
                archive.add(directory / 'surrogates.joblib', arcname='surrogates.joblib', recursive=False)
        release = github.repo('POST', '/releases', {
            'tag_name': 'core-damage-analysis-' + os.environ['GITHUB_RUN_ID'],
            'target_commitish': manifest['source_sha'], 'name': 'Core damage analysis · ' + phase,
            'draft': False, 'prerelease': True})
        archive = ReleaseArchive(github, release['id']).publish(directory, attempt=phase, complete=True)
        manifest.setdefault('analysis_archives', []).append({'phase': phase, 'archive': archive,
                                                            'release_url': release['html_url']})
        if phase == 'confirmation':
            manifest['final_report_url'] = release['html_url']
    persist(store, manifest)


if __name__ == '__main__':
    main()
