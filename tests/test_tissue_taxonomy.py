from __future__ import annotations

import json

import pytest

from src.training.tissue_taxonomy import TissueTaxonomyError, load_tissue_taxonomy


def _taxonomy_payload() -> dict:
    return {
        "schema_version": "1.0",
        "taxonomy_version": "test",
        "status": "provisional",
        "clinically_validated": False,
        "ignore_index": 255,
        "ignore_color_rgb": [147, 51, 234],
        "classes": [
            {
                "value": 0,
                "key": "background",
                "label_pt_br": "Fundo",
                "trainable": True,
                "color_rgb": [0, 0, 0],
                "definition": "Fora da ferida",
            },
            {
                "value": 1,
                "key": "granulation",
                "label_pt_br": "Granulação",
                "trainable": True,
                "color_rgb": [220, 38, 38],
                "definition": "Definição provisória",
            },
        ],
        "deferred_classes": ["epithelialization"],
    }


def test_load_tissue_taxonomy_preserves_ignore_index(tmp_path):
    path = tmp_path / "taxonomy.json"
    path.write_text(json.dumps(_taxonomy_payload()), encoding="utf-8")

    taxonomy = load_tissue_taxonomy(path)

    assert taxonomy.num_classes == 2
    assert taxonomy.allowed_mask_values == (0, 1, 255)
    assert taxonomy.classes[1].color_rgb == (220, 38, 38)
    assert taxonomy.ignore_color_rgb == (147, 51, 234)
    assert not taxonomy.clinically_validated


def test_taxonomy_rejects_unvalidated_epithelialization(tmp_path):
    payload = _taxonomy_payload()
    payload["classes"].append(
        {
            "value": 2,
            "key": "epithelialization",
            "label_pt_br": "Epitelização",
            "trainable": True,
            "definition": "Ainda não validada",
        }
    )
    path = tmp_path / "taxonomy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(TissueTaxonomyError, match="clinical validation"):
        load_tissue_taxonomy(path)


def test_taxonomy_rejects_non_contiguous_trainable_values(tmp_path):
    payload = _taxonomy_payload()
    payload["classes"][1]["value"] = 3
    path = tmp_path / "taxonomy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(TissueTaxonomyError, match="contiguous"):
        load_tissue_taxonomy(path)
