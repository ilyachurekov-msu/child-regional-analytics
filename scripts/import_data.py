import argparse
from sqlalchemy.orm import Session
from app.db import engine
from app.etl.importer import import_file


def main():
    parser = argparse.ArgumentParser(
        description="Импорт нормализованного официального CSV/XLSX/JSON"
    )
    parser.add_argument("file")
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--publisher", default="Росстат")
    args = parser.parse_args()
    with Session(engine()) as session, session.begin():
        batch = import_file(
            session, args.file, args.source_url, args.source_name, args.publisher
        )
        print(
            f"{batch.batch_id}: {batch.status}; строк {batch.rows_processed}, ошибок {batch.errors}"
        )


if __name__ == "__main__":
    main()
