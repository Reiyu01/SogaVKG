怎麼用?
直接將下面範本貼至到test_query_builder.py的query中



1. 只查特定欄位
query = {
    "entity": "Asset",
    "fields": ["asset_code", "name"]
}


2. 加上排序 (order_by)
query = {
    "entity": "Asset",
    "fields": ["asset_code", "name", "quantity"],
    "order_by": {
        "field": "quantity",
        "direction": "DESC"
    },
    "limit": 5
}

3. 完全不寫 fields（預設全選）
query = {
    "entity": "Asset",
    "filters": {
        "status": "in_use"
    }
}

4. 查詢其他實體 (entity)
query = {
    "entity": "Category",
    "fields": ["name"],
    "filters": {
        "name": "電子"
    }
}

5. 模糊關鍵字搜索
query = {
    "entity": "Asset",

    "fields": [
        "asset_code",
        "name",
        "quantity",
        "status",
        "category",
        "location",
    ],

    "filters": {
        "name": "ESP32",
        "location": "C217",
    },

    "limit": 20,
}



怎麼用?
直接將下面範本貼至到test_query_builder2.py的query中

1. 查 ESP32
SemanticQuery(
    entity="Asset",
    fields=[
        "name",
        "quantity",
    ],
    filters=[
        QueryFilter(
            field="name",
            operator="LIKE",
            value="ESP32",
        )
    ]
)

2. 查數量小於 5
SemanticQuery(
    entity="Asset",
    fields=[
        "name",
        "quantity",
    ],
    filters=[
        QueryFilter(
            field="quantity",
            operator="<",
            value=5,
        )
    ]
)
預期輸出: WHERE a.quantity < :filter_0

3. 查 C217 的 Sensor
SemanticQuery(
    entity="Asset",
    fields=[
        "name",
        "quantity",
        "category",
        "location",
    ],
    filters=[
        QueryFilter(
            field="category",
            operator="LIKE",
            value="Sensor",
        ),
        QueryFilter(
            field="location",
            operator="LIKE",
            value="C217",
        ),
    ],
)