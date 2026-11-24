"""Russian analytical UI; no observations are created by the interface."""

from pathlib import Path
import httpx
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from app.config import settings
from app.services.analytics import construct_index

st.set_page_config(page_title="Региональная аналитика", layout="wide")
st.title("Региональная аналитика")
st.caption("Навигатор детства · открытая официальная статистика · контракт 1.0.0")


def get(route, **params):
    try:
        response = httpx.get(
            settings().api_url + "/api/v1/" + route,
            params={k: v for k, v in params.items() if v is not None},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        st.error(f"Не удалось получить данные API: {exc}")
        st.stop()


def all_values(**params):
    result, offset = [], 0
    while True:
        data = get("regional/values", limit=1000, offset=offset, **params)
        result.extend(data["items"])
        offset += len(data["items"])
        if offset >= data["total"] or not data["items"]:
            return result


def frame(rows):
    df = pd.DataFrame(rows)
    if not df.empty:
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["year"] = df["period_start"].str[:4].astype(int)
    return df


def chart(df, indicator):
    if df.empty:
        st.info(
            "Для выбранного региона и периода официальные значения ещё не загружены."
        )
        return
    figure = px.line(
        df.sort_values("period_start"),
        x="year",
        y="value",
        color="region_name",
        markers=True,
        labels={"year": "Год", "value": indicator["unit"], "region_name": "Регион"},
        title=indicator["name"],
    )
    figure.update_traces(connectgaps=False)
    figure.update_layout(xaxis={"dtick": 1})
    st.plotly_chart(figure, use_container_width=True)
    st.caption(
        f"Период: {df['period_start'].min()} — {df['period_end'].max()} · Единица: {indicator['unit']}"
    )
    for name, url in (
        df[["source_name", "source_url"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    ):
        st.markdown(f"Источник: [{name}]({url})" if url else f"Источник: {name}")


regions = get("regions", limit=1000)["items"]
indicators = get("regional/indicators")["items"]
region_names = {r["region_id"]: r["name"] for r in regions}
indicator_names = {i["code"]: i["name"] for i in indicators}
page = st.sidebar.radio(
    "Раздел",
    [
        "Главная",
        "Карта России",
        "Паспорт региона",
        "Сравнение регионов",
        "Динамика показателей",
        "Качество и актуальность данных",
        "Экспорт аналитической справки",
    ],
    key='page',
)
code = st.sidebar.selectbox(
    "Показатель", list(indicator_names), format_func=indicator_names.get
)
indicator = next(i for i in indicators if i["code"] == code)
quality = get("regional/data-quality", limit=10)
if not quality["current_observations"]:
    st.warning(
        "Реальные статистические значения ещё не загружены. Демонстрационные данные не используются."
    )

if page == "Главная":
    st.subheader("Положение детей и семей в регионах")
    c1, c2, c3 = st.columns(3)
    c1.metric("Регионов в справочнике", len(regions))
    c2.metric("Показателей в каталоге", len(indicators))
    c3.metric("Загруженных наблюдений", quality["current_observations"])
    st.write(
        "Выберите регион, изучите динамику и сравните опубликованные значения. Итоги по России и федеральным округам показываются только при наличии официальных агрегатов."
    )
    st.dataframe(
        pd.DataFrame(indicators)[["name", "unit", "description"]],
        hide_index=True,
        use_container_width=True,
    )
    with st.expander("Методология выбранного показателя"):
        st.write(indicator["methodology"])
    with st.expander("Конструктор исследовательского индекса"):
        st.warning(
            "Индекс не является официальной оценкой благополучия. Нормирование зависит от выбранной совокупности и весов. Пропуски не заполняются."
        )
        year = st.number_input("Год индекса", 2019, 2100, 2023)
        selected = st.multiselect(
            "Показатели индекса", list(indicator_names), format_func=indicator_names.get
        )
        weights, directions = {}, {}
        for item in selected:
            weights[item] = st.number_input(
                "Вес: " + indicator_names[item],
                min_value=0.01,
                value=1.0,
                key="weight_" + item,
            )
            directions[item] = st.selectbox(
                "Благоприятное направление: " + indicator_names[item],
                ["positive", "negative"],
                format_func=lambda d: "Рост" if d == "positive" else "Снижение",
                key="direction_" + item,
            )
        if st.button("Рассчитать выбранный индекс"):
            rows = all_values(year=year)
            matrix = {}
            for row in rows:
                if row["region_id"].startswith("RU-"):
                    matrix.setdefault(row["region_name"], {})[row["indicator_code"]] = (
                        float(row["value"]) if row["value"] is not None else None
                    )
            try:
                scores = construct_index(matrix, weights, directions)
                st.dataframe(
                    pd.DataFrame(
                        [{"Регион": r, "Индекс (0–100)": s} for r, s in scores.items()]
                    ),
                    hide_index=True,
                )
                st.json(
                    {
                        "year": year,
                        "weights": weights,
                        "directions": directions,
                        "method": "min-max; полные наблюдения; 0–100",
                    }
                )
            except ValueError as exc:
                st.error(str(exc))

elif page in (
    "Паспорт региона",
    "Динамика показателей",
    "Экспорт аналитической справки",
):
    region_id = st.selectbox("Регион", list(region_names), format_func=region_names.get, key='profile_region')
    if page == "Паспорт региона":
        profile = get("regional/profiles/" + region_id)
        st.subheader(region_names[region_id])
        st.caption(profile["note"])
        df = frame(profile["observations"])
        if not df.empty:
            own = df[df.region_id == region_id]
            if not own.empty:
                latest_year = own.year.max()
                st.write(f"Последний период региона: {latest_year}")
                st.dataframe(
                    own[own.year == latest_year][
                        ["indicator_name", "value", "unit", "source_name"]
                    ],
                    hide_index=True,
                )
            chart(df[df.indicator_code == code], indicator)
        else:
            st.info("Паспорт ожидает загрузки официальных наблюдений.")
    elif page == "Динамика показателей":
        chart(frame(all_values(region_id=region_id, indicator_code=code)), indicator)
    else:
        rows = all_values(region_id=region_id)
        df = frame(rows)
        text = f"# Аналитическая справка\n\nРегион: {region_names[region_id]}\n\n"
        if df.empty:
            text += "Официальные наблюдения не загружены; статистические выводы невозможны.\n"
        else:
            for item in indicators:
                series = df[df.indicator_code == item["code"]].sort_values("year")
                if not series.empty:
                    row = series.iloc[-1]
                    text += f"- {item['name']}: {row['value'] if pd.notna(row['value']) else 'нет данных'} {item['unit']} ({row['year']}). Источник: {row['source_name']}, {row['source_url']}.\n"
            text += "\nАбсолютные показатели зависят от размера региона; причинные выводы и интегральная оценка не делаются.\n"
        st.markdown(text)
        st.download_button(
            "Скачать справку Markdown", text.encode("utf-8"), "regional-report.md"
        )
        for fmt in ("csv", "xlsx"):
            from app.services.export import export_rows

            st.download_button(
                "Скачать " + fmt.upper(), export_rows(rows, fmt), "regional." + fmt
            )

elif page == "Сравнение регионов":
    selected = st.multiselect(
        "Выберите от 2 до 5 регионов",
        list(region_names),
        default=list(region_names)[:2],
        max_selections=5,
        format_func=region_names.get,
    )
    if len(selected) < 2:
        st.info("Выберите хотя бы два региона.")
    else:
        data = get("regional/comparison", region_ids=selected, indicator_code=code)
        df = frame(data["items"])
        chart(df, indicator)
        if not df.empty:
            st.dataframe(df.pivot(index="year", columns="region_name", values="value"))
        st.caption(
            "Изменение между двумя последними доступными наблюдениями; при нулевой базе относительное изменение не определяется."
        )
        st.dataframe(
            pd.DataFrame(
                [{"Регион": region_names[r], **v} for r, v in data["changes"].items()]
            ),
            hide_index=True,
        )

elif page == "Карта России":
    available = frame(all_values(indicator_code=code))
    latest_year = int(available.year.max()) if not available.empty else 2023
    year = st.number_input("Год", 1900, 2100, latest_year)
    df = frame(all_values(indicator_code=code, year=year))
    geography = Path("data/regions.geojson.gz")
    if geography.exists():
        from app.services.geography import geography as load_geography
        geo, provenance = load_geography()
        st.caption('Границы: geoBoundaries / OpenStreetMap, 2017, ODbL 1.0. Покрытие: 83 региона; отсутствуют ' + ', '.join(provenance['missing_regions']))
        # Offline choropleth; no tiles or third-party network required.
        base = pd.DataFrame(regions)
        values = (
            df[["region_id", "value"]]
            if not df.empty
            else pd.DataFrame(columns=["region_id", "value"])
        )
        merged = base.merge(values, on="region_id", how="left")
        fig = go.Figure(
            go.Choropleth(
                geojson=geo,
                featureidkey="properties.region_id",
                locations=merged.region_id,
                z=[0] * len(merged),
                colorscale=[[0, "#d1d5db"], [1, "#d1d5db"]],
                showscale=False,
                text=merged.name,
                customdata=merged.region_id,
                hovertemplate="%{text}: нет данных<extra></extra>",
            )
        )
        valid = merged[merged.value.notna()]
        fig.add_trace(
            go.Choropleth(
                geojson=geo,
                featureidkey="properties.region_id",
                locations=valid.region_id,
                z=valid.value,
                text=valid.name,
                customdata=valid.region_id,
                colorscale="Blues",
                colorbar_title=indicator["unit"],
                hovertemplate="%{text}: %{z}<extra></extra>",
            )
        )
        fig.update_geos(fitbounds="locations", visible=False)
        def select_on_map():
            points = st.session_state['regional_map']['selection']['points']
            if points:
                selected_region = points[0].get('location') or points[0].get('customdata')
                if selected_region in region_names:
                    st.session_state['profile_region'] = selected_region
                    st.session_state['page'] = 'Паспорт региона'

        st.plotly_chart(fig, use_container_width=True, key='regional_map', on_select=select_on_map)
        st.caption(f"{year} · {indicator['unit']} · Серый цвет: нет данных")
    else:
        st.info(
            "Географические границы ещё не подключены. Для автономной карты требуется проверенный data/regions.geojson с properties.region_id. Доступные значения показаны ниже."
        )
    if not df.empty:
        st.dataframe(
            df[["region_name", "value", "unit", "source_name", "source_url"]],
            hide_index=True,
        )
    deviations = get("regional/deviations", indicator_code=code, year=year)
    st.subheader("Отклонения от медианы субъектов")
    st.caption(deviations["warning"])
    st.dataframe(pd.DataFrame(deviations["items"]), hide_index=True)

else:
    st.subheader("Качество и актуальность данных")
    data = get("regional/data-quality", limit=1000)
    st.write("Последняя загрузка:", data["latest_load"] or "отсутствует")
    st.write("Журнал загрузок")
    st.dataframe(pd.DataFrame(data["batches"]), hide_index=True)
    st.write("Ошибки, пропуски и очередь сопоставления регионов")
    st.dataframe(pd.DataFrame(data["items"]), hide_index=True)
    st.caption(
        "Для исправления сопоставления добавьте проверенный вариант в contracts/region_aliases.json; пересчёт требует повышения версии загрузчика. История сохраняется."
    )
