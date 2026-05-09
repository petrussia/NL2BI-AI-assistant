# Local mirror final sync v2

_Generated: 2026-04-30T14:38:33.007726+00:00_

The agent will rebuild the local mirror by:
1. Base64-encoding `/content/drive/MyDrive/diploma_plan_sql/exports/latest_tz_closure.tar.gz` through the bridge `/exec` endpoint.
2. Saving the b64 to `C:\\temp\\tarball_b64.json`.
3. Decoding to `C:\\temp\\latest_tz_closure.tar.gz`.
4. Extracting into `d:\\HSE\\Диплом\\NL2BI-AI-assistant\\` with `tar -xzf --overwrite`.
5. Copying the tarball to `tools/backups/latest_final_maximized_v2.tar.gz`.

After sync the local mirror contains:
- 29 prediction files (one per run)
- 14 evaluation modules in `repo/src/evaluation/`
- 12 thesis-pack files in `outputs/thesis_pack_shubin/`
- 7 bundled docs in `outputs/docs/`
- 13+ figures in `outputs/plots/`
- Refreshed REPORT.md (v4)
- Updated DeepSeek blocker artifacts
- New Qwen-14B runtime attempt log + comparison tables
