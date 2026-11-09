# 計畫：README 加入應用截圖

> 狀態：**已完成（2026-11-09）**
> 最終決策：使用者確認只用 3 張主視圖（卡片牆／列表／詳情頁），卡片圖 IP 顯示「-」用現圖不重拍。
> 產物：[README.md](../README.md) 新增「畫面」小節（104 → 112 行）、`docs\screenshots\` 三張 PNG、路徑驗證全部可解析。

## 1. 素材盤點與取捨

| 檔案 | 尺寸 | 判斷 | 理由 |
|------|------|------|------|
| `wsl_desk_card.png` | 1196×712 | **採用** | 卡片牆主視圖，7 台實例、1 台執行中 |
| `wsl_desk_list.png` | 1196×721 | **採用** | 表格視圖，IP 欄有真實值 192.168.163.232 |
| `wsl_desk_instance_detail.png` | 1196×712 | **採用** | 詳情頁，執行中狀態、操作列分組、網路規則區 |
| `wsl_desk_add_instance1.png` | 682×502 | **採用** | 精靈步驟 1／3，三種來源選項一目了然 |
| `wsl_desk_add_instance2.png` | 682×502 | **採用** | 精靈步驟 2／3，檔案選擇 |
| `wsl_desk_add_instance3.png` | 682×502 | **採用** | 精靈步驟 3／3，命名與安裝位置 |
| `wsl_desk_setting1.png` | 642×752 | **採用** | 全域設定，目錄／保留策略 |
| `wsl_desk_instance_setting1.png` | 642×752 | **採用** | Instance 設定，預設使用者／systemd／網路隔離 |
| `wsl_desk_setting2.png` | 642×752 | 略過 | 全域設定捲動後的續段（一般＋SOCKS5），與 setting1 重疊 |
| `wsl_desk_instance_setting2.png` | 642×752 | 略過 | Instance 設定捲動後的續段（進階維護），與 setting1 重疊 |

合計採用 **8 張**，總重約 270 KB，載入無負擔。

## 2. 觀察事項（不阻塞，供您判斷）

1. **卡片牆 IP 欄仍是「-」**：Ubuntu-26.04 明明是執行中，列表與詳情頁都有 192.168.163.232，但卡片牆那張的 IP 顯示「-」。若非刻意，這是產品端卡片 IP 未刷新；README 用了列表圖已能佐證 IP 功能，但卡片圖會被細心讀者注意到。
2. **`alms` 名稱只在卡片圖露出**：列表圖的 alms 打了馬賽克、卡片圖則清楚顯示。若不介意就維持；若在意名稱一致，需重拍其一。
3. **詳情頁安裝路徑部分打碼**：與列表／精靈一致，屬刻意處理，保留。

## 3. 變更內容

### 3.1 圖片落點

```
docs\screenshots\
    wsl_desk_card.png
    wsl_desk_list.png
    wsl_desk_instance_detail.png
    wsl_desk_add_instance1.png
    wsl_desk_add_instance2.png
    wsl_desk_add_instance3.png
    wsl_desk_setting1.png
    wsl_desk_instance_setting1.png
```

檔名維持原樣，不做重新編號，減少對照成本。倉庫根目錄原有的舊 `wsl_desk_*.png`（若還在）一併移除，避免兩份。

### 3.2 README 插入內容

位置：開頭兩段之後、`## 功能` 之前。新增約 20 行，README 由 104 行增至約 124 行。

```markdown
## 畫面

首頁兩種檢視，右上角切換：

| 卡片牆 | 列表 | 詳情頁 |
|:---:|:---:|:---:|
| ![卡片牆](docs/screenshots/wsl_desk_card.png) | ![列表](docs/screenshots/wsl_desk_list.png) | ![詳情頁](docs/screenshots/wsl_desk_instance_detail.png) |

新增實例是三步精靈：官方發行版直接 `wsl --install`，rootfs/tar 或 VHDX 則從本機檔案匯入。

| 步驟 1 · 選擇來源 | 步驟 2 · 選擇檔案 | 步驟 3 · 命名與位置 |
|:---:|:---:|:---:|
| ![步驟1](docs/screenshots/wsl_desk_add_instance1.png) | ![步驟2](docs/screenshots/wsl_desk_add_instance2.png) | ![步驟3](docs/screenshots/wsl_desk_add_instance3.png) |

設定分兩層：全域設定管目錄骨架、輪詢間隔、主題與代理；Instance 設定管預設使用者、systemd、`/etc/wsl.conf` 與網路隔離。

| 全域設定 | Instance 設定 |
|:---:|:---:|
| ![全域設定](docs/screenshots/wsl_desk_setting1.png) | ![Instance 設定](docs/screenshots/wsl_desk_instance_setting1.png) |
```

## 4. 不做的事

- 不動 LICENSE、程式碼、`.gitignore`（`docs/` 本來就納入版控）。
- 不用 `setting2`、`instance_setting2`。
- 不為截圖加 lightbox 腳本（GitHub 表格內圖片點擊即開原圖）。

## 5. 驗收

1. `docs\screenshots\` 恰有 8 張 PNG，倉庫根目錄無殘留 `wsl_desk_*.png`。
2. README 所有 `docs/screenshots/` 相對路徑皆能對上實際檔名。
3. Markdown 預覽：三列圖片併排、無破圖。

## 6. 回滾

刪除 `docs\screenshots\`、移除 README「畫面」小節即可。

## 7. 待確認

| # | 問題 | 預設 |
|---|------|------|
| Q1 | 採用張數 | 8 張（略過 2 張捲動重複圖） |
| Q2 | 排版 | 三列表格併排 |
| Q3 | 小節標題 | `## 畫面` |
| Q4 | 是否先處理卡片圖 IP 為「-」 | 先用現圖，之後您想重拍再覆蓋同名檔即可 |
