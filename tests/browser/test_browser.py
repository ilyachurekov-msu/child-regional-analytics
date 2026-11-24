from pathlib import Path
import pytest

pytestmark = pytest.mark.browser


def test_seven_pages_and_screenshots(page):
    from playwright.sync_api import expect

    output = Path("test-results/screenshots")
    page.set_viewport_size({'width': 1440, 'height': 1100})
    output.mkdir(parents=True, exist_ok=True)
    page.goto("http://localhost:8501")
    expect(
        page.get_by_role("heading", name="Региональная аналитика", exact=True)
    ).to_be_visible(timeout=60000)
    pages = [
        "Главная",
        "Карта России",
        "Паспорт региона",
        "Сравнение регионов",
        "Динамика показателей",
        "Качество и актуальность данных",
        "Экспорт аналитической справки",
    ]
    for index, name in enumerate(pages):
        page.get_by_test_id("stSidebar").get_by_text(name, exact=True).click()
        expected = {
            "Главная": "Положение детей и семей в регионах",
            "Карта России": "Отклонения от медианы субъектов",
            "Сравнение регионов": "Выберите от 2 до 5 регионов",
            "Качество и актуальность данных": "Журнал загрузок",
            "Экспорт аналитической справки": "Скачать справку Markdown",
        }
        if name in expected:
            expect(page.get_by_text(expected[name], exact=False).first).to_be_visible(
                timeout=30000
            )
        else:
            expect(
                page.get_by_role("combobox", name="Регион", exact=True)
            ).to_be_visible(timeout=30000)
        if name in (
            "Паспорт региона",
            "Динамика показателей",
            "Экспорт аналитической справки",
        ):
            region = page.get_by_role("combobox", name="Регион", exact=True)
            region.click()
            region.fill("Кемеровская")
            page.get_by_role(
                "option", name="Кемеровская область — Кузбасс", exact=True
            ).click()
            if name == "Динамика показателей":
                expect(page.get_by_test_id("stPlotlyChart")).to_have_count(
                    1, timeout=30000
                )
        expect(page.get_by_test_id("stException")).to_have_count(0)
        if name == 'Карта России':
            expect(page.locator('.maplibregl-canvas')).to_be_visible(timeout=30000)
            page.wait_for_function('''() => {
                const p = document.querySelector('.js-plotly-plot');
                const map = p?._fullLayout?.map?._subplot?.map;
                return map && map.loaded() && map.queryRenderedFeatures().length >= 1;
            }''', timeout=60000)
            expect(page.get_by_text('Серый цвет: нет данных', exact=False)).to_be_visible()
        expect(page.get_by_role("radio", name=name, exact=True)).to_be_checked()
        page.screenshot(path=str(output / f"{index + 1}.png"), full_page=True)
