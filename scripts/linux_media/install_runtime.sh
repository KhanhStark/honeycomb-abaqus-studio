set -euo pipefail
media="$RUNNER_TEMP/abaqus-media-inspection/iso/DS.SIMULIA.Suite.2020.Linux64_Softgozar.com.iso"
echo "d0b227290b5f62ea826b08c18bde222417817fc0d04b91abb0072cb52ebe43ad  $media" | sha256sum -c -
mkdir -p "$RUNNER_TEMP/abaqus-mount" output/install-probe
sudo chown 1000:1000 output/install-probe
sudo mount -o loop,ro "$media" "$RUNNER_TEMP/abaqus-mount"
docker volume create honeycomb-install
optional_caa=()
if [[ "${HONEYCOMB_INSTALL_CAA:-0}" == "1" ]]; then
  optional_caa=(--env HONEYCOMB_INSTALL_CAA=1)
fi
docker run --label honeycomb.actions=true --rm --network none --cap-drop ALL --security-opt no-new-privileges \
  "${optional_caa[@]}" \
  --pids-limit 512 --memory 8g \
  --mount "type=bind,source=$RUNNER_TEMP/abaqus-mount,target=/media,readonly" \
  --mount "type=bind,source=$PWD/output/install-probe,target=/results" \
  --mount type=volume,source=honeycomb-install,target=/opt \
  honeycomb-install-probe
