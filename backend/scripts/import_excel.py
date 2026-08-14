from pathlib import Path
import sqlite3
import sys
from typing import Any

import pandas as pd


# ============================================================
# Project paths
# ============================================================

# backend/scripts/import_excel.py
#     ↓
# backend/
#     ↓
# project root = ../..
BASE_DIR = Path(__file__).resolve().parents[1]

EXCEL_PATH = BASE_DIR / "data" / "raw" / "輸出.xlsx"
DB_PATH = BASE_DIR / "data" / "lab.db"


# ============================================================
# Helpers
# ============================================================

def clean_value(value: Any) -> Any:
    """
    清理 Excel 儲存格內容。

    處理：
    - NaN
    - None
    - 空字串
    - 只有空白的字串

    回傳：
    - None
    - stripped string
    - 原始值
    """
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, str):
        value = value.strip()

        if value == "":
            return None

        return value

    return value


def clean_string(value: Any) -> str | None:
    """
    將內容轉成乾淨字串。
    """
    value = clean_value(value)

    if value is None:
        return None

    return str(value).strip()


def clean_number(value: Any, default: float = 0) -> float:
    """
    將 Excel 數值轉成 float。

    None / NaN / 無法轉換時回傳 default。
    """
    value = clean_value(value)

    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clean_integer(value: Any, default: int = 0) -> int:
    """
    將 Excel 欄位轉成整數。

    常用於：
    - Boolean 欄位
    - 紀錄編號
    """
    value = clean_value(value)

    if value is None:
        return default

    if isinstance(value, bool):
        return int(value)

    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def clean_boolean(value: Any) -> int:
    """
    將 Excel 中的各種真假值轉成 SQLite 使用的 0 / 1。

    支援：
    True / False
    1 / 0
    是 / 否
    Y / N
    Yes / No
    true / false
    """
    value = clean_value(value)

    if value is None:
        return 0

    if isinstance(value, bool):
        return int(value)

    if isinstance(value, (int, float)):
        return 1 if value != 0 else 0

    value_str = str(value).strip().lower()

    true_values = {
        "1",
        "true",
        "t",
        "yes",
        "y",
        "是",
        "有",
        "已",
        "已歸還",
        "已還",
    }

    false_values = {
        "0",
        "false",
        "f",
        "no",
        "n",
        "否",
        "無",
        "未",
        "未歸還",
        "未還",
    }

    if value_str in true_values:
        return 1

    if value_str in false_values:
        return 0

    # 無法判斷時預設 False
    return 0


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """
    檢查 SQLite table 是否存在。
    """
    row = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()

    return row is not None


# ============================================================
# Category / Location
# ============================================================

def get_or_create_category(
    conn: sqlite3.Connection,
    category_name: str | None,
) -> int | None:
    """
    取得 Category ID。
    不存在就建立。
    """
    if not category_name:
        return None

    conn.execute(
        """
        INSERT OR IGNORE INTO categories (name)
        VALUES (?)
        """,
        (category_name,),
    )

    row = conn.execute(
        """
        SELECT id
        FROM categories
        WHERE name = ?
        """,
        (category_name,),
    ).fetchone()

    if row is None:
        return None

    return row[0]


def get_or_create_location(
    conn: sqlite3.Connection,
    location_name: str | None,
) -> int | None:
    """
    取得 Location ID。
    不存在就建立。
    """
    if not location_name:
        return None

    conn.execute(
        """
        INSERT OR IGNORE INTO locations (name)
        VALUES (?)
        """,
        (location_name,),
    )

    row = conn.execute(
        """
        SELECT id
        FROM locations
        WHERE name = ?
        """,
        (location_name,),
    ).fetchone()

    if row is None:
        return None

    return row[0]


# ============================================================
# Validate sheets
# ============================================================

def validate_required_columns(
    df: pd.DataFrame,
    required_columns: list[str],
    sheet_name: str,
) -> None:
    """
    檢查 Excel 工作表是否包含必要欄位。
    """
    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"\n工作表「{sheet_name}」缺少必要欄位：\n"
            + "\n".join(f"  - {column}" for column in missing_columns)
        )


# ============================================================
# Import Assets
# ============================================================

def import_assets(conn: sqlite3.Connection) -> dict[str, int]:
    """
    匯入「資產清單_整合」。

    對應 SQLite：
        assets
        categories
        locations
    """
    sheet_name = "資產清單_整合"

    print()
    print("=" * 60)
    print(f"開始處理：{sheet_name}")
    print("=" * 60)

    df = pd.read_excel(
        EXCEL_PATH,
        sheet_name=sheet_name,
    )

    required_columns = [
        "資產編號",
        "編號類型",
        "品名",
        "財產類別",
        "存放地點",
        "數量",
        "狀態",
        "規格",
        "備註",
        "來源分頁",
        "重複ID警示",
    ]

    validate_required_columns(
        df,
        required_columns,
        sheet_name,
    )

    print(f"Excel 資料筆數：{len(df)}")

    imported_count = 0
    skipped_count = 0
    missing_asset_code_count = 0
    duplicate_warning_count = 0

    for excel_row_number, (_, row) in enumerate(
        df.iterrows(),
        start=2,
    ):
        # ----------------------------------------------------
        # 基本欄位
        # ----------------------------------------------------

        asset_code = clean_string(
            row["資產編號"]
        )

        code_type = clean_string(
            row["編號類型"]
        )

        asset_name = clean_string(
            row["品名"]
        )

        category_name = clean_string(
            row["財產類別"]
        )

        location_name = clean_string(
            row["存放地點"]
        )

        quantity = clean_number(
            row["數量"],
            default=0,
        )

        status = clean_string(
            row["狀態"]
        )

        specification = clean_string(
            row["規格"]
        )

        note = clean_string(
            row["備註"]
        )

        source_sheet = clean_string(
            row["來源分頁"]
        )

        duplicate_warning = clean_boolean(
            row["重複ID警示"]
        )

        # ----------------------------------------------------
        # 必填資料檢查
        # ----------------------------------------------------

        # 品名是 Asset 的核心欄位。
        # 沒有品名的資料不建立 Asset。
        if not asset_name:
            print(
                f"[SKIP] Excel row {excel_row_number}: "
                f"品名為空，略過此筆資料。"
            )

            skipped_count += 1
            continue

        # 資產編號不是系統內部 ID。
        # 因此可以不存在。
        if not asset_code:
            missing_asset_code_count += 1

            print(
                f"[WARNING] Excel row {excel_row_number}: "
                f"缺少資產編號，品名={asset_name}"
            )

        if duplicate_warning:
            duplicate_warning_count += 1

        # ----------------------------------------------------
        # Category
        # ----------------------------------------------------

        category_id = get_or_create_category(
            conn,
            category_name,
        )

        # ----------------------------------------------------
        # Location
        # ----------------------------------------------------

        location_id = get_or_create_location(
            conn,
            location_name,
        )

        # ----------------------------------------------------
        # Insert Asset
        # ----------------------------------------------------

        conn.execute(
            """
            INSERT INTO assets (
                asset_code,
                code_type,
                name,
                category_id,
                location_id,
                quantity,
                status,
                specification,
                note,
                source_sheet,
                duplicate_warning
            )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                asset_code,
                code_type,
                asset_name,
                category_id,
                location_id,
                quantity,
                status,
                specification,
                note,
                source_sheet,
                duplicate_warning,
            ),
        )

        imported_count += 1

    result = {
        "excel_count": len(df),
        "imported_count": imported_count,
        "skipped_count": skipped_count,
        "missing_asset_code_count": missing_asset_code_count,
        "duplicate_warning_count": duplicate_warning_count,
    }

    print()
    print("資產清單匯入完成：")
    print(f"  Excel 筆數             : {result['excel_count']}")
    print(f"  成功匯入               : {result['imported_count']}")
    print(f"  略過                   : {result['skipped_count']}")
    print(f"  缺少資產編號           : {result['missing_asset_code_count']}")
    print(f"  有重複 ID 警示         : {result['duplicate_warning_count']}")

    return result


# ============================================================
# Import Borrow Records
# ============================================================

def import_borrow_records(
    conn: sqlite3.Connection,
) -> dict[str, int]:
    """
    匯入「借用紀錄_整合」。

    對應 SQLite：
        borrow_records
    """
    sheet_name = "借用紀錄_整合"

    print()
    print("=" * 60)
    print(f"開始處理：{sheet_name}")
    print("=" * 60)

    df = pd.read_excel(
        EXCEL_PATH,
        sheet_name=sheet_name,
    )

    required_columns = [
        "紀錄編號",
        "時間戳記",
        "借用人Email",
        "經手人",
        "品名（已還原其他欄）",
        "原填設備編號",
        "配對到的資產編號",
        "配對到的資產品名",
        "配對狀態",
        "備註說明",
        "數量",
        "數量為推測值",
        "用途",
        "使用地點",
        "出借日期",
        "歸還日期",
        "已歸還",
        "原始備註",
    ]

    validate_required_columns(
        df,
        required_columns,
        sheet_name,
    )

    print(f"Excel 資料筆數：{len(df)}")

    imported_count = 0
    skipped_count = 0
    pending_review_count = 0
    unlisted_count = 0
    matched_count = 0

    for excel_row_number, (_, row) in enumerate(
        df.iterrows(),
        start=2,
    ):
        # ----------------------------------------------------
        # 讀取與清理資料
        # ----------------------------------------------------

        record_no_value = clean_value(
            row["紀錄編號"]
        )

        record_no = clean_integer(
            record_no_value,
            default=0,
        )

        timestamp = clean_string(
            row["時間戳記"]
        )

        borrower_email = clean_string(
            row["借用人Email"]
        )

        handler = clean_string(
            row["經手人"]
        )

        item_name = clean_string(
            row["品名（已還原其他欄）"]
        )

        original_asset_code = clean_string(
            row["原填設備編號"]
        )

        matched_asset_code = clean_string(
            row["配對到的資產編號"]
        )

        matched_asset_name = clean_string(
            row["配對到的資產品名"]
        )

        match_status = clean_string(
            row["配對狀態"]
        )

        note = clean_string(
            row["備註說明"]
        )

        quantity = clean_number(
            row["數量"],
            default=0,
        )

        quantity_estimated = clean_boolean(
            row["數量為推測值"]
        )

        purpose = clean_string(
            row["用途"]
        )

        usage_location = clean_string(
            row["使用地點"]
        )

        borrow_date = clean_string(
            row["出借日期"]
        )

        return_date = clean_string(
            row["歸還日期"]
        )

        returned = clean_boolean(
            row["已歸還"]
        )

        original_note = clean_string(
            row["原始備註"]
        )

        # ----------------------------------------------------
        # 最基本資料檢查
        # ----------------------------------------------------

        # 如果整筆資料幾乎完全空白，略過。
        if (
            item_name is None
            and original_asset_code is None
            and borrower_email is None
            and timestamp is None
        ):
            print(
                f"[SKIP] Excel row {excel_row_number}: "
                f"借用紀錄內容為空。"
            )

            skipped_count += 1
            continue

        # ----------------------------------------------------
        # 統計 match status
        # ----------------------------------------------------

        normalized_status = (
            match_status.lower()
            if match_status
            else ""
        )

        if "matched" in normalized_status:
            matched_count += 1

        if (
            "pending_review" in normalized_status
            or "pending" in normalized_status
            or "待核對" in normalized_status
        ):
            pending_review_count += 1

        if (
            "unlisted" in normalized_status
            or "未列管" in normalized_status
        ):
            unlisted_count += 1

        # ----------------------------------------------------
        # Insert Borrow Record
        # ----------------------------------------------------

        conn.execute(
            """
            INSERT INTO borrow_records (
                record_no,
                timestamp,
                borrower_email,
                handler,
                item_name,
                original_asset_code,
                matched_asset_code,
                matched_asset_name,
                match_status,
                note,
                quantity,
                quantity_estimated,
                purpose,
                usage_location,
                borrow_date,
                return_date,
                returned,
                original_note
            )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                record_no,
                timestamp,
                borrower_email,
                handler,
                item_name,
                original_asset_code,
                matched_asset_code,
                matched_asset_name,
                match_status,
                note,
                quantity,
                quantity_estimated,
                purpose,
                usage_location,
                borrow_date,
                return_date,
                returned,
                original_note,
            ),
        )

        imported_count += 1

    result = {
        "excel_count": len(df),
        "imported_count": imported_count,
        "skipped_count": skipped_count,
        "matched_count": matched_count,
        "pending_review_count": pending_review_count,
        "unlisted_count": unlisted_count,
    }

    print()
    print("借用紀錄匯入完成：")
    print(f"  Excel 筆數             : {result['excel_count']}")
    print(f"  成功匯入               : {result['imported_count']}")
    print(f"  略過                   : {result['skipped_count']}")
    print(f"  matched                : {result['matched_count']}")
    print(f"  pending_review         : {result['pending_review_count']}")
    print(f"  unlisted               : {result['unlisted_count']}")

    return result


# ============================================================
# Database cleanup
# ============================================================

def clear_imported_data(
    conn: sqlite3.Connection,
) -> None:
    """
    清除本次 Excel 匯入會產生的資料。

    這是 MVP 階段使用。

    好處：
    每次重新執行 import_excel.py
    都可以得到乾淨的一份資料，不會重複 INSERT。

    未來正式環境應該改成：
        upsert
        migration
        ETL pipeline
    """
    print()
    print("=" * 60)
    print("清除舊匯入資料")
    print("=" * 60)

    # 先刪有 FK 關係的資料
    conn.execute(
        "DELETE FROM borrow_records"
    )

    conn.execute(
        "DELETE FROM assets"
    )

    conn.execute(
        "DELETE FROM categories"
    )

    conn.execute(
        "DELETE FROM locations"
    )

    print("舊資料清除完成。")


# ============================================================
# Verification
# ============================================================

def verify_database(
    conn: sqlite3.Connection,
) -> None:
    """
    匯入完成後檢查資料筆數。
    """
    print()
    print("=" * 60)
    print("Database 驗證")
    print("=" * 60)

    tables = [
        "assets",
        "categories",
        "locations",
        "borrow_records",
    ]

    for table in tables:

        if not table_exists(conn, table):
            print(
                f"[ERROR] Table 不存在：{table}"
            )
            continue

        row = conn.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()

        count = row[0] if row else 0

        print(
            f"{table:<20} : {count}"
        )

    # --------------------------------------------------------
    # Asset data quality
    # --------------------------------------------------------

    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM assets
        WHERE asset_code IS NULL
        """
    ).fetchone()

    missing_asset_code = (
        row[0]
        if row
        else 0
    )

    print(
        f"{'asset_code NULL':<20} : {missing_asset_code}"
    )

    # --------------------------------------------------------
    # Duplicate warning
    # --------------------------------------------------------

    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM assets
        WHERE duplicate_warning = 1
        """
    ).fetchone()

    duplicate_warning = (
        row[0]
        if row
        else 0
    )

    print(
        f"{'duplicate warning':<20} : {duplicate_warning}"
    )

    # --------------------------------------------------------
    # Borrow status
    # --------------------------------------------------------

    status_rows = conn.execute(
        """
        SELECT
            match_status,
            COUNT(*) AS count
        FROM borrow_records
        GROUP BY match_status
        ORDER BY count DESC
        """
    ).fetchall()

    print()
    print("借用紀錄配對狀態：")

    if not status_rows:
        print("  無資料")
    else:
        for row in status_rows:
            print(
                f"  {row[0]!r:<25} : {row[1]}"
            )


# ============================================================
# Main
# ============================================================

def main() -> None:
    print("=" * 60)
    print("Laboratory Data Platform")
    print("Excel → SQLite Import")
    print("=" * 60)

    # --------------------------------------------------------
    # Check Excel
    # --------------------------------------------------------

    if not EXCEL_PATH.exists():
        print()
        print(
            f"[ERROR] 找不到 Excel：\n"
            f"{EXCEL_PATH}"
        )
        sys.exit(1)

    print()
    print(f"Excel：{EXCEL_PATH}")
    print(f"DB   ：{DB_PATH}")

    # --------------------------------------------------------
    # Check Database
    # --------------------------------------------------------

    if not DB_PATH.exists():
        print()
        print(
            "[ERROR] 找不到 SQLite Database。"
        )
        print(
            "請先執行："
        )
        print(
            "python scripts/init_database.py"
        )
        sys.exit(1)

    # --------------------------------------------------------
    # Connect
    # --------------------------------------------------------

    conn = sqlite3.connect(DB_PATH)

    # --------------------------------------------------------
    # Transaction
    # --------------------------------------------------------

    try:
        # SQLite foreign key
        conn.execute(
            "PRAGMA foreign_keys = ON"
        )

        # ----------------------------------------------------
        # Clear old imported data
        # ----------------------------------------------------

        clear_imported_data(conn)

        # ----------------------------------------------------
        # Import Assets
        # ----------------------------------------------------

        asset_result = import_assets(conn)

        # ----------------------------------------------------
        # Import Borrow Records
        # ----------------------------------------------------

        borrow_result = import_borrow_records(conn)

        # ----------------------------------------------------
        # Commit
        # ----------------------------------------------------

        conn.commit()

        print()
        print("=" * 60)
        print("所有資料匯入成功")
        print("=" * 60)

        # ----------------------------------------------------
        # Verify
        # ----------------------------------------------------

        verify_database(conn)

        # ----------------------------------------------------
        # Final summary
        # ----------------------------------------------------

        print()
        print("=" * 60)
        print("Import Summary")
        print("=" * 60)

        print(
            f"Assets               : "
            f"{asset_result['imported_count']}"
        )

        print(
            f"Borrow Records       : "
            f"{borrow_result['imported_count']}"
        )

        print(
            f"Missing Asset Code   : "
            f"{asset_result['missing_asset_code_count']}"
        )

        print(
            f"Duplicate Warning    : "
            f"{asset_result['duplicate_warning_count']}"
        )

        print(
            f"Pending Review       : "
            f"{borrow_result['pending_review_count']}"
        )

        print(
            f"Unlisted             : "
            f"{borrow_result['unlisted_count']}"
        )

        print()
        print(
            f"SQLite database：{DB_PATH}"
        )

    except Exception as exc:

        # ----------------------------------------------------
        # Rollback
        # ----------------------------------------------------

        conn.rollback()

        print()
        print("=" * 60)
        print("匯入失敗")
        print("=" * 60)

        print(
            f"{type(exc).__name__}: {exc}"
        )

        raise

    finally:
        conn.close()


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    main()