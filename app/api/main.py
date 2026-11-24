from app.contract_version import CONTRACT_VERSION
from typing import Annotated, Literal
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from app.db import get_session
from app.models.entities import Batch, Indicator, QualityIssue, Region, Value
from app.schemas.api import ErrorOut, IndicatorOut, ObservationOut, Page, RegionOut
from app.services.analytics import change, deviations, observation, observations_query
from app.services.export import export_rows

app = FastAPI(
    title="Региональная аналитика",
    version="0.2.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    responses={
        400: {"model": ErrorOut},
        404: {"model": ErrorOut},
        422: {"model": ErrorOut},
        500: {"model": ErrorOut},
    },
)
DB = Annotated[Session, Depends(get_session)]
Limit = Annotated[int, Query(ge=1, le=1000)]
Offset = Annotated[int, Query(ge=0)]
Year = Annotated[int | None, Query(ge=1900, le=2100)]


@app.get("/api/v1/regional/indicator-metadata")
def indicator_metadata(session: DB):
    import json
    from pathlib import Path

    cards = json.loads(
        Path("contracts/indicator-metadata.json").read_text(encoding="utf-8")
    )
    stats = {
        code: (last, count)
        for code, last, count in session.execute(
            select(
                Indicator.code, func.max(Value.loaded_at), func.count(Value.value_id)
            )
            .join(Value, Value.indicator_id == Indicator.indicator_id)
            .where(Value.is_current.is_(True))
            .group_by(Indicator.code)
        )
    }
    for card in cards:
        last, count = stats.get(card["code"], (None, 0))
        card["last_successful_load"] = last
        card["observations_loaded"] = count
    return {"items": cards, "total": len(cards)}


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": str(exc.status_code),
                "message": str(exc.detail),
                "details": [],
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Некорректные параметры запроса",
                "details": jsonable_encoder(
                    exc.errors(), custom_encoder={ValueError: str}
                ),
            }
        },
    )


@app.exception_handler(Exception)
async def internal_error(request, exc):
    import logging

    logging.getLogger(__name__).exception("API failure", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "Внутренняя ошибка сервера",
                "details": [],
            }
        },
    )


def page(session, query, limit, offset, transform=lambda r: r):
    total = session.scalar(
        select(func.count()).select_from(query.order_by(None).subquery())
    )
    return dict(
        items=[
            transform(r) for r in session.execute(query.limit(limit).offset(offset))
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/api/v1/health")
def health(session: DB):
    session.execute(text("SELECT 1"))
    return {"status": "ok", "contract_version": CONTRACT_VERSION}


@app.get("/api/v1/regions", response_model=Page[RegionOut])
def regions(
    session: DB,
    limit: Limit = 100,
    offset: Offset = 0,
    federal_district: str | None = None,
    subjects_only: bool = True,
):
    query = select(Region)
    if subjects_only:
        query = query.where(Region.region_id.like("RU-%"))
    if federal_district:
        query = query.where(Region.federal_district == federal_district)
    return page(session, query.order_by(Region.name), limit, offset, lambda r: r[0])


@app.get("/api/v1/regions/{region_id}", response_model=RegionOut)
def region(region_id: str, session: DB):
    result = session.get(Region, region_id)
    if not result:
        raise HTTPException(404, "Регион не найден")
    return result


@app.get("/api/v1/regional/indicators", response_model=Page[IndicatorOut])
def indicators(
    session: DB, limit: Limit = 100, offset: Offset = 0, topic_id: str | None = None
):
    query = select(Indicator).where(Indicator.is_active.is_(True))
    if topic_id:
        query = query.where(Indicator.topic_id == topic_id)
    return page(session, query.order_by(Indicator.code), limit, offset, lambda r: r[0])


@app.get("/api/v1/regional/values", response_model=Page[ObservationOut])
def values(
    session: DB,
    limit: Limit = 100,
    offset: Offset = 0,
    region_id: str | None = None,
    indicator_code: str | None = None,
    year: Year = None,
    history: bool = False,
):
    return page(
        session,
        observations_query(
            [region_id] if region_id else None, indicator_code, year, history
        ),
        limit,
        offset,
        observation,
    )


@app.get("/api/v1/regional/profiles/{region_id}")
def profile(region_id: str, session: DB, year: Year = None):
    subject = region(region_id, session)
    district = session.scalar(
        select(Region).where(
            Region.region_id.like("FD-%"),
            Region.federal_district == subject.federal_district,
        )
    )
    ids = list(
        dict.fromkeys([region_id, "RU"] + ([district.region_id] if district else []))
    )
    data = [observation(r) for r in session.execute(observations_query(ids, year=year))]
    return {
        "region": RegionOut.model_validate(subject).model_dump(),
        "observations": data,
        "note": "РФ и ФО показаны только при наличии опубликованных агрегатов; суммы субъектов не подменяют официальные итоги.",
    }


@app.get("/api/v1/regional/comparison")
def comparison(
    session: DB,
    region_ids: Annotated[list[str], Query(min_length=2, max_length=5)],
    indicator_code: str,
    year: Year = None,
):
    if len(set(region_ids)) != len(region_ids):
        raise HTTPException(422, "Регионы не должны повторяться")
    for region_id in region_ids:
        region(region_id, session)
    rows = [
        observation(r)
        for r in session.execute(observations_query(region_ids, indicator_code, year))
    ]
    changes = {}
    for region_id in region_ids:
        series = [r for r in rows if r["region_id"] == region_id]
        changes[region_id] = (
            change(series[-2]["value"], series[-1]["value"])
            if len(series) > 1
            else change(None, None)
        )
    return {"items": rows, "changes": changes}


@app.get("/api/v1/regional/deviations")
def deviation_api(
    session: DB, indicator_code: str, year: Annotated[int, Query(ge=1900, le=2100)]
):
    indicator = session.scalar(
        select(Indicator).where(Indicator.code == indicator_code)
    )
    if not indicator:
        raise HTTPException(404, "Показатель не найден")
    rows = [
        observation(r)
        for r in session.execute(
            observations_query(indicator_code=indicator_code, year=year)
        )
    ]
    return {
        "items": deviations(rows, indicator.direction),
        "warning": "Медиана рассчитана только по субъектам с загруженными данными, а не по всей России. Сравнение абсолютных величин зависит от размера региона. При неоднозначном направлении рейтинг неблагополучия не определяется.",
    }


@app.get("/api/v1/regional/data-quality")
def quality(
    session: DB,
    limit: Limit = 100,
    offset: Offset = 0,
    resolution_status: str | None = None,
):
    query = select(QualityIssue)
    if resolution_status:
        query = query.where(QualityIssue.resolution_status == resolution_status)
    result = page(
        session,
        query.order_by(QualityIssue.issue_id),
        limit,
        offset,
        lambda r: {
            c.name: getattr(r[0], c.name) for c in QualityIssue.__table__.columns
        },
    )
    result["batches"] = [
        {c.name: getattr(b, c.name) for c in Batch.__table__.columns}
        for b in session.scalars(
            select(Batch).order_by(Batch.loaded_at.desc()).limit(limit).offset(offset)
        )
    ]
    result["current_observations"] = session.scalar(
        select(func.count()).select_from(Value).where(Value.is_current.is_(True))
    )
    result["latest_load"] = session.scalar(select(func.max(Value.loaded_at)))
    coverage = session.execute(
        select(
            Region.region_id, Region.name, func.count(Value.value),
            func.count(func.distinct(Value.period_start)),
            func.count(func.distinct(Value.indicator_id)),
            func.min(Value.period_start), func.max(Value.period_end),
        ).outerjoin(Value, (Value.region_id == Region.region_id) &
                    Value.is_current.is_(True) & Value.value.is_not(None))
        .where(Region.region_id.like("RU-%"))
        .group_by(Region.region_id, Region.name).order_by(Region.name)
    ).all()
    result["region_coverage"] = [
        dict(region_id=r[0], name=r[1], observations=r[2], periods=r[3],
             indicators=r[4], first_period=r[5], last_period=r[6]) for r in coverage
    ]
    result["regions_in_profile"] = len(coverage)
    result["regions_with_data"] = sum(r[2] > 0 for r in coverage)
    return result


@app.get("/api/v1/regional/export")
def export(
    session: DB,
    region_id: str | None = None,
    indicator_code: str | None = None,
    year: Year = None,
    format: Literal["csv", "xlsx"] = "csv",
):
    query = observations_query([region_id] if region_id else None, indicator_code, year)
    rows = session.execute(query.limit(100001)).all()
    if len(rows) > 100000:
        raise HTTPException(400, "Экспорт ограничен 100000 строк. Уточните фильтры.")
    data = export_rows([observation(r) for r in rows], format)
    return Response(
        data,
        media_type="text/csv; charset=utf-8"
        if format == "csv"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="regional.{format}"'},
    )
