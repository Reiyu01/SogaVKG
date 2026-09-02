操作說明先創建虛擬環境後執行
python -r requirements.txt
接著檢查scripts/clean_data下是否有兩張xlsx原始資料集
若有執行
python clean_ucl_data.py 財產清單.xlsx 財產借用單.xlsx 輸出.xlsx

其輸出檔案會儲存於data/raw/輸出.xlsx下

接著執行scripts/init_database.py來建置資料表會建立data/lab.db
成功後執行scripts/import_excel.py將輸出.xlsx會進去資料表lab.db中

都成功後接著cd 至./backend後 執行python -m scripts.test_query_builder
即可看到產出結果

若需要更改情境可參照scripts/demo情境範本.md
將query複製貼上至test_query_builder即可

目前只進展至回傳組合SQL，未實際呼叫SQL

為甚麼不要直接映射成SQL而是要經過成本體yaml方式?
1. 若建置資料過於複雜(如要經過跨表鏈結)對於使用者來說定義其SQL過於繁雜，使用本體概念相較於使用者來說相當直覺
2. SQL無法再其上添加各種增加檢索功用的技術，如向量化
3. SQL無法使用類似圖遍歷技術