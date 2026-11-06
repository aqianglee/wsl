# Plan：首頁增加 IP + 佔用大小 & 窗口最大化

> 狀態：待確認

---

## 目標

1. 應用啟動時預設**最大化**（保留 Windows 工作列）
2. 首頁列表（InstanceTable）增加 **IP**（150px）和 **大小**（100px）兩欄
3. 卡片（InstanceCard）採用**方案 C**：底部按鈕上方加兩個膠囊 stat strip（IP / 大小）
4. `Distro` 資料模型補上 `ip` 欄位

---

## 涉及文件

| 文件 | 改動 |
|------|------|
| `wsl-deck/app/ui/main_window.py` | `resize(1000,680)` → `showMaximized()`；需引入 `QGuiApplication` |
| `wsl-deck/app/wsl.py` | `Distro` dataclass 增加 `ip: str = ""` |
| `wsl-deck/app/ui/instance_card.py` | 卡片高度 185→~220；新增 stat strip（IP + 大小膠囊） |
| `wsl-deck/app/ui/instance_table.py` | 新增 IP 欄位(150px) + 大小欄位(100px)；header 同步調整；`BUTTONS_WIDTH` 保持不變 |
| `wsl-deck/app/ui/card_wall.py` | `CARD_MIN_WIDTH` 可能需要小幅上調（280→320）以適應加高後卡片 |

---

## 詳細設計

### 1. 窗口最大化（main_window.py:109）

```python
# 之前
self.resize(1000, 680)

# 之後
self.resize(1200, 720)  # 保留 fallback 初始尺寸
# ...其他控件初始化完成後...
QTimer.singleShot(0, self.showMaximized)
```

> 用 `QTimer.singleShot(0, ...)` 確保事件循環啟動後才最大化，避免某些平台上 UI 尚未佈局就被截斷。

### 2. Distro 補 ip 欄位（wsl.py:25-33）

```python
@dataclass(frozen=True)
class Distro:
    name: str
    state: str
    version: int
    is_default: bool
    guid: str
    base_path: str
    vhdx_path: str
    vhdx_size: int
    ip: str = ""          # ← 新增，running 時由 refresh 流程填入
```

> `ip` 預設空字串，因為 `list_distros()` 本身**不**查 IP（太昂貴）。
> IP 需要在 refresh 後**非同步**獲取（參考現有 `_refresh_network` 模式），或者只在用戶點進詳細頁時才查。
> 
> **討論**：卡片/列表都在首頁顯示，如果每個 instance 都查 IP，首次載入會慢。建議：
> - **running 的 instance**：在 refresh 時批量查 IP（非同步，查到後更新卡片/列表）
> - **stopped 的 instance**：顯示 `-` 或空白

### 3. 列表欄位調整（instance_table.py）

目前結構：`分隔 | 圖標(40) | 分隔 | 名稱(stretch) | 分隔 | 操作(412) | 分隔`

調整後：`分隔 | 圖標(40) | 分隔 | 名稱(stretch) | 分隔 | IP(150) | 分隔 | 大小(100) | 分隔 | 操作(412) | 分隔`

**Header 同步**：在 "名稱" 和 "操作" 之間插入 "IP"、"大小" 兩個 header label。

**InstanceRow**：
- 在 `_name` 和 `ops` 之間插入 `_ip_label`（Consolas 字體，150px，灰色）和 `_size_label`（右對齊，100px）
- `update_distro()` 中填入 `distro.ip` 和 `f"{distro.size_gb:.1f} GB"`
- 若 `running=False`，IP 顯示 `-`

**常量調整**：
```python
IP_COLUMN_WIDTH = 150
SIZE_COLUMN_WIDTH = 100
# OPS_COLUMN_WIDTH = BUTTONS_WIDTH + COLUMN_PADDING * 2  保持不變
```

### 4. 卡片 Stat Strip（instance_card.py）

**卡片高度 185 → 220**（增加 35px 左右容納 stat strip）

**新結構**：
```
┌──────────────────────────────────────────────┐
│  ★  [系統]                      [⏻] [>_]    │  header
│                                              │  +20px spacing
│              Ubuntu-24.04                    │  name (18px 粗體居中, 不變)
│                                              │  +8px spacing
│  ┌─────────────┐     ┌──────────────┐       │  stat strip (膠囊樣式)
│  │ 172.28.123.45│     │   12.4 GB     │       │  IP 膠囊  +  大小 膠囊
│  └─────────────┘     └──────────────┘       │
│                                              │  stretch
│   [Linux 檔案]        [安裝目錄]             │  footer (不變)
└──────────────────────────────────────────────┘
```

**膠囊樣式**：
- 圓角矩形（border-radius 10px）
- 淺灰色背景 `rgba(128,128,128,30)`
- 1px 灰邊框
- 內容水平垂直居中，小字（pointSize 9）
- IP 用 Consolas 等寬字體
- 若 stopped，IP 膠囊顯示 `-`

**stat strip 組件**：
```python
# 新增常量
STAT_PILL_HEIGHT = 26
STAT_PILL_RADIUS = 10
```

---

## 跟進調整 ⑥：卡片按設計圖重構（左對齊 + 單行資訊 + 左對齊按鈕）

> 狀態：**已執行**

**設計圖**：

```
┌─────────────────────────────────────────┐
│  ❤️                           ⏻  >_    │
│  Ubuntu-26.04                           │  名稱：左對齊
│  📦 2.5 GB              192.168.163.232 │  資訊：單行水平，容量左、IP 右
│  [Linux 檔案]    [安裝目錄]              │  按鈕：左對齊
└─────────────────────────────────────────┘
```

**與現況對比**：

| 元素 | 現況 | 改後 |
|------|------|------|
| 名稱 | `AlignCenter` | `AlignLeft` |
| 資訊 | `QVBoxLayout` 兩行居中 | `QHBoxLayout` 單行：容量左、stretch、IP 右 |
| 容量文字 | `"2.5 GB"` | 前加圖示（`SP_DriveHDIcon`） |
| footer | `stretch + 按鈕 + 按鈕`（靠右） | `按鈕 + 按鈕 + stretch`（靠左） |

**改動文件**：`instance_card.py`

| 行 | 原 | 改為 |
|----|----|------|
| L149 | `self._name.setAlignment(Qt.AlignCenter)` | `Qt.AlignLeft` |
| L156-L175 | `QVBoxLayout stat_col`（兩行） | `QHBoxLayout stat_row`（容量 + stretch + IP） |
| L164 | 無圖示 | 容量 label 前加 `SP_DriveHDIcon`，`setIconSize(QSize(12,12))` |
| L181 | `footer.addStretch(1)`（最前） | 移到 `footer` 最後（靠左） |
| L163/L171 | `AlignCenter` | 容量 `AlignLeft`、IP `AlignRight` |

---

## 跟進調整 ⑤：按鈕縮窄＋卡片按鈕右對齊＋操作列收窄

> 狀態：**已確認（按鈕寬度 100px）**

**需求**：
1. 「Linux 檔案 / 安裝目錄」按鈕寬度適當縮小（卡片與表格同步）
2. 卡片內按鈕改為**靠右對齊**
3. 表格操作列寬度同步收窄

**尺寸計算**（表格操作列）：

```
詳情 64 + 電源 26 + 終端 26 + Linux檔案 100 + 安裝目錄 100 = 316
按鈕間距 8 × 4 = 32
左右 padding 12 × 2 = 24
→ OPS_COLUMN_WIDTH = 372
→ BUTTONS_WIDTH = 372 - 24 = 348
```

**改動**：

| 文件 | 項目 | 原 | 新 |
|------|------|----|----|
| `instance_table.py` | `BUTTONS_WIDTH` | 388 | **348** |
| `instance_table.py` | 兩個按鈕 | `setFixedSize(120, 26)` | `setFixedSize(100, 26)` |
| `instance_card.py` | 兩個按鈕 | `setFixedSize(120, 26)` | `setFixedSize(100, 26)` |
| `instance_card.py` | footer 佈局 | `stretch + 按鈕 + stretch`（居中） | `stretch + 按鈕`（**靠右**） |
| 高度 | 26px | 26px | 不變 |

---

## 跟進調整 ④：卡片按鈕尺寸對齊表格

> 狀態：**已執行**

**需求**：卡片內「Linux 檔案」「安裝目錄」兩個按鈕，**寬高都**要與 table 中一致。

**基準**（`instance_table.py`）：

```python
self._linux_btn.setFixedSize(120, ICON_BUTTON_SIZE)   # 120 × 26
```

**改動**（`instance_card.py`）：

| 項目 | 原 | 新 |
|------|----|----|
| Linux 檔案 | `setFixedHeight(40)` + `setMinimumWidth(120)` | `setFixedSize(120, ICON_BUTTON_SIZE)` |
| 安裝目錄 | `setFixedHeight(40)` + `setMinimumWidth(120)` | `setFixedSize(120, ICON_BUTTON_SIZE)` |
| 常量 `ACTION_BUTTON_HEIGHT = 40` | 存在 | **刪除**（已無引用） |
| 圖標尺寸 | 16 × 16 | 不變（與表格一致） |
| QSS 樣式 | `#cardAction`（padding/border-radius 與 `#rowAction` 相同） | 不變 |

按鈕高度由 40 → **26px**，省下的 14px 由名稱下方拉伸吸收，**卡片高度仍為 185px**。

---

## 跟進調整 ③：改為兩行居中（上排容量、下排 IP）

> 狀態：**已執行**

**需求**：資訊改為上下兩行、水平居中；**容量在上一行，IP 在下一行**。

**改動**（`instance_card.py` L156-L176）：

| 項目 | 原（單行左右） | 新（兩行居中） |
|------|--------------|--------------|
| 容器 | `QHBoxLayout`（IP 左 / 大小 右） | `QVBoxLayout`（`spacing=2`） |
| 順序 | IP → 大小 | **大小（上）→ IP（下）** |
| 對齊 | `AlignLeft` / `AlignRight` | 兩者皆 `AlignCenter` |
| 樣式 | 灰色小字 `#7a7a7a` 9pt | 不變 |

**效果**：

```
┌──────────────────────────────────────┐
│  ★                     [⏻] [>_]     │
│            wsl-tomcat9               │
│                                      │
│                2.4 GB                │  ← 上：容量
│            192.168.163.232           │  ← 下：IP
│                                      │
│    [Linux 檔案]      [安裝目錄]       │
└──────────────────────────────────────┘
```

卡片高度 185px 不變。

---

## 跟進調整 ②：膠囊改為方案 A（灰色小字，無膠囊）

> 狀態：**已執行**

**需求**：不用膠囊樣式，回到方案 A——名稱下方一行灰色小字，IP 靠左、大小靠右。

**改動**（`instance_card.py`）：

| 項目 | 原（方案 C 膠囊） | 新（方案 A 小字） |
|------|------------------|------------------|
| 容器 | 兩個 `QLabel` 加背景/邊框/圓角 | 兩個 `QLabel` **純文字**，無背景 |
| 字色 | `#555` + 半透明底 | `#7a7a7a`（`STAT_TEXT_COLOR`） |
| 對齊 | 居中一組 | **IP 靠左、大小靠右**（中間 stretch） |
| 常量 | `STAT_PILL_HEIGHT` / `STAT_PILL_RADIUS` | 刪除，改 `STAT_TEXT_COLOR` |
| `_pill_style()` | 存在 | 刪除（已無用） |
| 垂直間距 | name → 膠囊 伸縮、膠囊 → 按鈕 12px | **維持不變**（伸縮在 name 下方、按鈕上方 12px） |
| 卡片高度 | 185px | **185px 不變** |

**效果**：

```
┌──────────────────────────────────────┐
│  ★                     [⏻] [>_]     │
│                                      │
│            wsl-tomcat9               │
│                                      │
│  192.168.163.232            2.4 GB   │  ← 灰色小字，無膠囊
│                                      │
│    [Linux 檔案]      [安裝目錄]       │
└──────────────────────────────────────┘
```

---

## 跟進調整 ①：膠囊垂直位置

> 狀態：**已確認（膠囊→按鈕間距 12px）**

**需求**：兩個膠囊**靠近下方按鈕**、**遠離上方 name**。

**現況**（[instance_card.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/instance_card.py#L143-L187)）：

| 位置 | 現在 | 說明 |
|------|------|------|
| name → 膠囊 | `addSpacing(6)` | 固定 6px，太近 |
| 膠囊 → 按鈕 | `addStretch(1)` | 吸收約 26px 剩餘空間，太遠 |

**改動**（僅調整伸縮位置，不改任何樣式與高度）：

| 行 | 原 | 改為 |
|----|----|------|
| L155 | `layout.addSpacing(6)` | `layout.addStretch(1)` |
| L185 | `layout.addStretch(1)` | `layout.addSpacing(12)` |

**效果**：

```
┌──────────────────────────────────────┐
│  ★                     [⏻] [>_]     │
│                                      │
│            wsl-tomcat9               │  name
│                                      │  ← 伸縮空間 ~26px（拉開）
│  ┌──────────────┐  ┌────────────┐    │
│  │192.168.163.232│  │   2.4 GB    │    │  膠囊
│  └──────────────┘  └────────────┘    │
│                                      │  ← 固定 6px（貼近）
│    [Linux 檔案]      [安裝目錄]       │  footer
└──────────────────────────────────────┘
```

卡片高度仍為 **185px**，樣式與其他元素皆不動。

### 5. CardWall CARD_MIN_WIDTH

卡片加高了但不加寬，`CARD_MIN_WIDTH = 280` 暫時不變。如果後續發現卡片在狹窄窗口下被擠扁，再考慮上調到 320。

---

## 執行順序

1. `Distro` dataclass 補 `ip` 欄位（含 refresh 時查 IP 的非同步邏輯）
2. InstanceTable 列表欄位 + header 調整（含常量）
3. InstanceCard 卡片 stat strip 實作 + 樣式
4. CardWall 高度適配（被動，自動）
5. main_window 最大化改動
6. 驗證：啟動應用 → 最大化 → 檢查列表和卡片

---

## 風險與取捨

| 項目 | 風險 | 取捨 |
|------|------|------|
| IP 查詢 | `hostname -I` 每個 running instance ~1-2s，同步卡 UI | 非同步批量查詢，查到後更新顯示；stopped 顯示 `-` |
| 表格欄位過多 | 150 + 100 + 40 + 412 = 702px 固定欄 + 3 條分隔線 | 最大化後至少 1000+px 可用，足夠 |
| 卡片高度增加 | 從 185→220，滿屏時顯示行數減少 | 權衡信息密度 vs 美觀，先試 |

---

**請確認：**
1. IP 非同步策略（running 才查，stopped 顯示 `-`）OK 嗎？
2. 卡片高度 185→220 可以接受嗎？
3. 還有其他調整嗎？
