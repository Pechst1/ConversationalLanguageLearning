"""WP-165: the shared season-plate interface (keys, prompt, the never-waiting lookup)."""

from app.services.season import plates


def test_plate_key_orders_parts_and_drops_unknown_values():
    assert plates.plate_key("odile_flat") == "season:odile_flat"
    assert plates.plate_key("quai_de_valmy", time_of_day="night", weather="rain") == "season:quai_de_valmy:night:rain"
    assert plates.plate_key("le_mistral", time_of_day="teatime") == "season:le_mistral"
    assert plates.plate_key("le_mistral", day="2026-10-12 Grève!") == "season:le_mistral:2026-10-12-gr-ve"


def test_prompt_keeps_the_no_people_style():
    prompt = plates.prompt_for("Odile's flat, a piano under a sheet, a window on the canal, evening lamplight")
    assert "No people" in prompt
    assert "Odile's flat" in prompt


def test_lookup_falls_back_to_the_static_plate_without_a_session():
    assert plates.plate_url_for(None, "odile_flat", time_of_day="night") == "/assets/serial/locations/odile_flat.webp"
    assert plates.plate_url_for(None, None) is None
