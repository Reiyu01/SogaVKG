PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS maintenance_records;
DROP TABLE IF EXISTS borrow_records;
DROP TABLE IF EXISTS assets;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS locations;

CREATE TABLE locations (
  id INTEGER PRIMARY KEY,
  building TEXT NOT NULL,
  room TEXT NOT NULL,
  name TEXT NOT NULL,
  manager TEXT NOT NULL
);

CREATE TABLE categories (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT
);

CREATE TABLE assets (
  id INTEGER PRIMARY KEY,
  asset_code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  brand TEXT,
  model TEXT,
  quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 0),
  status TEXT NOT NULL CHECK (status IN ('available', 'borrowed', 'maintenance', 'retired')),
  purchase_date TEXT,
  category_id INTEGER NOT NULL,
  location_id INTEGER NOT NULL,
  note TEXT,
  FOREIGN KEY (category_id) REFERENCES categories(id),
  FOREIGN KEY (location_id) REFERENCES locations(id)
);

CREATE TABLE borrow_records (
  id INTEGER PRIMARY KEY,
  asset_id INTEGER NOT NULL,
  borrower_name TEXT NOT NULL,
  borrower_department TEXT NOT NULL,
  borrowed_at TEXT NOT NULL,
  due_at TEXT NOT NULL,
  returned_at TEXT,
  purpose TEXT,
  FOREIGN KEY (asset_id) REFERENCES assets(id)
);

CREATE TABLE maintenance_records (
  id INTEGER PRIMARY KEY,
  asset_id INTEGER NOT NULL,
  reported_at TEXT NOT NULL,
  completed_at TEXT,
  vendor TEXT,
  cost REAL DEFAULT 0,
  status TEXT NOT NULL CHECK (status IN ('open', 'in_progress', 'completed')),
  description TEXT NOT NULL,
  FOREIGN KEY (asset_id) REFERENCES assets(id)
);

INSERT INTO locations (id, building, room, name, manager) VALUES
  (1, '綜合大樓', 'C217', 'C217 智慧製造實驗室', '王小明'),
  (2, '綜合大樓', 'C218', 'C218 物聯網實驗室', '林怡君'),
  (3, '圖資大樓', 'B105', 'B105 多媒體教室', '陳志豪'),
  (4, '行政大樓', 'A301', 'A301 資訊中心', '許雅雯'),
  (5, '工程大樓', 'E402', 'E402 電子實驗室', '張家維');

INSERT INTO categories (id, name, description) VALUES
  (1, '感測器', '環境與量測用感測設備'),
  (2, '網路設備', '交換器、路由器與無線網路設備'),
  (3, '運算設備', '桌機、伺服器與邊緣運算設備'),
  (4, '多媒體設備', '攝影、投影與音訊設備'),
  (5, '實驗儀器', '電子與製造實驗使用儀器');

INSERT INTO assets (id, asset_code, name, brand, model, quantity, status, purchase_date, category_id, location_id, note) VALUES
  (1, 'SEN-001', '溫濕度感測器', 'Sensirion', 'SHT31', 12, 'available', '2025-03-12', 1, 1, 'C217 環境監測套件'),
  (2, 'SEN-002', '二氧化碳感測器', 'SenseAir', 'S8', 6, 'available', '2025-04-08', 1, 1, '教室空氣品質監測'),
  (3, 'SEN-003', '光照度感測器', 'Adafruit', 'TSL2591', 8, 'borrowed', '2024-11-20', 1, 2, 'IoT 課程實作'),
  (4, 'NET-001', '24 埠網路交換器', 'Cisco', 'CBS250-24T-4G', 2, 'available', '2024-08-15', 2, 4, '核心教學網路交換器'),
  (5, 'NET-002', '無線基地台', 'Ubiquiti', 'U6-Pro', 5, 'available', '2025-01-18', 2, 1, 'C217 與 C218 無線覆蓋'),
  (6, 'NET-003', '工業路由器', 'Moxa', 'EDR-G903', 1, 'maintenance', '2023-09-30', 2, 5, '韌體更新與網路異常檢修中'),
  (7, 'CMP-001', '邊緣 AI 運算盒', 'NVIDIA', 'Jetson Orin Nano', 4, 'available', '2025-02-25', 3, 1, '影像辨識與設備預測維護'),
  (8, 'CMP-002', 'GPU 工作站', 'Dell', 'Precision 5860', 2, 'available', '2024-06-10', 3, 2, 'AI 模型訓練'),
  (9, 'CMP-003', '資料庫伺服器', 'HPE', 'ProLiant DL360', 1, 'available', '2023-12-05', 3, 4, '校內教學系統資料庫'),
  (10, 'CMP-004', '迷你電腦', 'Raspberry Pi', 'Raspberry Pi 5', 10, 'borrowed', '2025-05-11', 3, 3, '嵌入式系統課程'),
  (11, 'MED-001', '4K 網路攝影機', 'Logitech', 'Brio 4K', 6, 'available', '2024-10-02', 4, 3, '遠距教學錄影'),
  (12, 'MED-002', '雷射投影機', 'Epson', 'EB-L260F', 2, 'available', '2023-07-15', 4, 3, '多媒體教室投影'),
  (13, 'MED-003', 'USB 麥克風', 'Rode', 'NT-USB Mini', 8, 'borrowed', '2025-03-05', 4, 2, 'Podcast 與專題錄音'),
  (14, 'INS-001', '數位示波器', 'Tektronix', 'TBS1052C', 3, 'available', '2024-02-21', 5, 5, '電子電路量測'),
  (15, 'INS-002', '桌上型電源供應器', 'Keysight', 'E36312A', 4, 'available', '2024-09-12', 5, 5, '三輸出可程式電源'),
  (16, 'INS-003', '3D 印表機', 'Bambu Lab', 'X1 Carbon', 2, 'maintenance', '2024-01-09', 5, 1, '其中一台需更換擠出機'),
  (17, 'SEN-004', '震動感測器', 'Bosch', 'BMA400', 10, 'available', '2025-06-01', 1, 5, '馬達健康監測實驗'),
  (18, 'NET-004', 'LoRaWAN 閘道器', 'RAK', 'WisGate Edge Pro', 2, 'available', '2025-04-22', 2, 2, '校園低功耗網路測試'),
  (19, 'CMP-005', 'NAS 儲存伺服器', 'Synology', 'DS923+', 1, 'available', '2024-12-18', 3, 4, '研究資料備份'),
  (20, 'MED-004', '360 度相機', 'Insta360', 'X4', 2, 'retired', '2022-05-10', 4, 3, '已汰換，保留盤點紀錄');

INSERT INTO borrow_records (id, asset_id, borrower_name, borrower_department, borrowed_at, due_at, returned_at, purpose) VALUES
  (1, 3, '李欣怡', '資訊工程系', '2026-09-15 09:00:00', '2026-09-25 17:00:00', NULL, '智慧教室專題'),
  (2, 10, '陳柏翰', '電子工程系', '2026-09-10 10:30:00', '2026-09-24 17:00:00', NULL, '嵌入式系統課程'),
  (3, 13, '黃郁婷', '創意設計系', '2026-09-18 13:00:00', '2026-09-30 17:00:00', NULL, '校園訪談錄音'),
  (4, 1, '吳承恩', '資訊工程系', '2026-08-20 09:00:00', '2026-08-27 17:00:00', '2026-08-26 15:20:00', '環境資料蒐集'),
  (5, 7, '林冠宇', '研究發展處', '2026-08-01 09:30:00', '2026-08-15 17:00:00', '2026-08-14 16:00:00', '邊緣 AI 展示'),
  (6, 14, '周品妤', '電子工程系', '2026-07-08 14:00:00', '2026-07-12 17:00:00', '2026-07-12 15:30:00', '電路實驗'),
  (7, 11, '張書豪', '通識教育中心', '2026-07-18 08:30:00', '2026-07-20 17:00:00', '2026-07-20 16:30:00', '研討會直播'),
  (8, 15, '許庭瑄', '電子工程系', '2026-06-03 09:00:00', '2026-06-05 17:00:00', '2026-06-05 16:50:00', '感測電路測試');

INSERT INTO maintenance_records (id, asset_id, reported_at, completed_at, vendor, cost, status, description) VALUES
  (1, 6, '2026-09-05 11:20:00', NULL, '摩莎網路', 0, 'in_progress', '工業路由器間歇性斷線，等待韌體與替換機測試'),
  (2, 16, '2026-09-12 14:10:00', NULL, '創想科技', 3500, 'open', '3D 印表機擠出機堵塞，需要更換零件'),
  (3, 12, '2026-06-10 09:00:00', '2026-06-13 16:00:00', '愛普生維修中心', 1800, 'completed', '投影機濾網與光學模組清潔'),
  (4, 8, '2026-05-02 10:40:00', '2026-05-04 15:00:00', '戴爾技術支援', 0, 'completed', 'GPU 工作站記憶體重新插拔與診斷');
