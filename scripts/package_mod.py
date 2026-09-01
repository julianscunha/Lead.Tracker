"""
Empacotamento do .mod (Fase 15).

`techforge package-module` (CLI oficial) exclui qualquer arquivo/pasta que
comece com ponto (EXCLUDE_PATTERNS, app/package_manager/builder.py) —
incluindo `.env-model`, que é obrigatório (docs/fases/03-CONFIGURACAO.md,
`sync_env()` em backend/main.py). Sem isso, install()/enable() quebram de
verdade num módulo instalado a partir do .mod (confirmado: FileNotFoundError).

Este script roda o build oficial e depois injeta `.env-model` no zip
resultante, regenerando o checksum sha256 sidecar — sem reinventar o
formato .mod, só completando o que o builder oficial descarta por engano.

Uso: python scripts/package_mod.py <staging_dir> <output_dir>
"""
from __future__ import annotations

import hashlib
import shutil
import sys
import zipfile
from pathlib import Path


def package(staging_dir: Path, output_dir: Path) -> Path:
    env_model = staging_dir / ".env-model"
    if not env_model.is_file():
        raise FileNotFoundError(f".env-model ausente em {staging_dir} — nada pra injetar")

    mod_files = sorted(output_dir.glob("*.mod"))
    if not mod_files:
        raise FileNotFoundError(f"Nenhum .mod encontrado em {output_dir} — rode 'techforge package-module' antes")
    mod_path = max(mod_files, key=lambda p: p.stat().st_mtime)

    with zipfile.ZipFile(mod_path, "a") as zf:
        if ".env-model" in zf.namelist():
            print(f"{mod_path.name} já tem .env-model, nada a fazer.")
        else:
            zf.write(env_model, ".env-model")
            print(f"Injetado .env-model em {mod_path.name}")

    checksum = hashlib.sha256(mod_path.read_bytes()).hexdigest()
    sidecar = mod_path.with_suffix(mod_path.suffix + ".sha256")
    sidecar.write_text(f"{checksum}  {mod_path.name}\n", encoding="utf-8")
    print(f"Checksum sha256 atualizado: {checksum[:16]}…")

    return mod_path


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python scripts/package_mod.py <staging_dir> <output_dir>")
        sys.exit(1)
    package(Path(sys.argv[1]), Path(sys.argv[2]))
