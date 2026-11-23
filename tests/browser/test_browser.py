from pathlib import Path
import pytest

pytestmark = pytest.mark.browser


def test_seven_pages_and_screenshots(page):
    from playwright.sync_api import expect

    output = Path("test-results/screenshots")
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
        expect(page.get_by_test_id("stException")).to_have_count(0)
        expect(page.get_by_role("radio", name=name, exact=True)).to_be_checked()
        page.screenshot(path=str(output / f"{index + 1}.png"), full_page=True)
