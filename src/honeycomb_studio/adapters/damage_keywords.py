# -*- coding: utf-8 -*-
"""Python 2.7 compatible solver-deck material contract, also used after CAE cloning."""
import re


def rewrite_input(path, config, materials):
    cards = dict((name.upper(), props['johnson_cook']) for name, props in materials.items()
                 if props.get('johnson_cook'))
    if not cards:
        return
    text = open(path).read()
    # Python 2.7 re.split ignores zero-width matches. Slice at finditer
    # offsets so the native Abaqus interpreter sees the same keyword blocks.
    offsets = [match.start() for match in re.finditer(r'(?m)^\*(?!\*)', text)]
    boundaries = sorted(set([0, len(text)] + offsets))
    blocks = [text[lo:hi] for lo, hi in zip(boundaries, boundaries[1:])]
    result = []
    current = None
    controls_written = False
    temperature_written = False
    seen = set()
    for block in blocks:
        first = block.split('\n', 1)[0].lower()
        if first.startswith('*material,'):
            current = re.search(r'name\s*=\s*([^,\r\n]+)', first).group(1).strip().upper()
            if not controls_written:
                result.append('*Section Controls, name=HC_DAMAGE, ELEMENT DELETION=YES\n1.,1.,1.\n')
                controls_written = True
        if first.startswith('*shell section'):
            lines = block.split('\n')
            lines[0] += ', CONTROLS=HC_DAMAGE'
            block = '\n'.join(lines)
        if first.startswith('*plastic') and current in cards:
            c = cards[current]
            block = ('*Plastic, hardening=JOHNSON COOK\n{A},{B},{n},{m},{melting_temperature},{transition_temperature}\n'
                     '*Rate Dependent, type=JOHNSON COOK\n{C},{reference_rate}\n'
                     '*Damage Initiation, criterion=JOHNSON COOK\n'
                     '{d1},{d2},{d3},{d4},{d5},{melting_temperature},{transition_temperature},{reference_rate}\n'
                     '*Damage Evolution, type=DISPLACEMENT, softening=LINEAR\n{failure_displacement_mm}\n'
                     '*Specific Heat\n{heat}\n*Inelastic Heat Fraction\n{inelastic_heat_fraction}\n').format(
                         heat=c['specific_heat_J_kg_K'] * 1.e6, **c)
            seen.add(current)
        if first.startswith('*step') and not temperature_written:
            result.append('*Initial Conditions, type=TEMPERATURE\nSANDWICH_NODES,%s\n' % config['initial_temperature_C'])
            temperature_written = True
        if first.startswith('*dynamic') and config.get('adiabatic'):
            lines = block.split('\n')
            lines[0] += ', ADIABATIC'
            block = '\n'.join(lines)
        if first.startswith('*energy output') and not re.search(r'\belset\s*=', first):
            # Preserve the requested global history, including ALLIHE which
            # CAE 2017 cannot create before the adiabatic step is injected.
            variables = config.get('history_variables')
            if variables:
                block = block.split('\n', 1)[0] + '\n' + ', '.join(variables) + '\n'
        result.append(block)
    if seen != set(cards) or not temperature_written:
        raise ValueError('Incomplete JC material injection; refusing solver input')
    with open(path, 'w') as stream:
        stream.write(''.join(result))
