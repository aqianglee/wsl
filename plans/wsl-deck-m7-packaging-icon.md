# M7 小計畫：安裝後桌面與開始菜單圖標與 App 內圖標一致

> 狀態：**已完成（2026-11-04）**
> 目標：安裝後的桌面捷徑、開始菜單捷徑（以及 exe 本身）顯示的圖標，與 App 視窗左上角圖標完全一致。

## 1. 已核實事實

- App 內圖標由 [app_icon.py](file:///d:/VirtualMachiles/wsl/wsl-deck/app/ui/app_icon.py#L9-L29) 以 QPainter 即時繪製：`#2d7ff9` 圓角方塊 + 白色粗體「Segoe UI」W，尺寸 16/24/32/48/64/128，**無任何外部圖檔**。
- [WSL Deck.spec](file:///d:/VirtualMachiles/wsl/wsl-deck/WSL%20Deck.spec#L15-L31) 的 `EXE()` **沒有 `icon=` 參數**，所以打包出的 `WSL Deck.exe` 內嵌的是 PyInstaller 預設圖標。
- [WSL Deck.iss](file:///d:/VirtualMachiles/wsl/wsl-deck/installer/WSL%20Deck.iss#L38-L40) 的 `[Icons]` 未指定 `IconFilename`，Inno Setup 預設取目標 exe 的內嵌圖標 → 桌面／開始菜單顯示的就是 PyInstaller 預設圖標。
- 專案內沒有任何 `.ico` 資源；根目錄 `WSL Deck.lnk` 的 `IconLocation` 也指向 `dist\WSL Deck\WSL Deck.exe,0`（同樣受 exe 圖標影響）。
- 已實測：用 `.venv` 的 Python（Windows 平台插件）離屏繪製該圖標可正常輸出「W」；在 `QT_QPA_PLATFORM=offscreen` 下字型庫缺失會畫成方框「tofu」，所以生成腳本**不能**強制 offscreen。

## 2. 變更範圍

| 檔案 | 變更 |
|------|------|
| `app/ui/app_icon.py` | 把繪製邏輯抽成 `app_pixmap(size)`；`ICON_SIZES` 增加 256（供資源管理器大圖標使用），`app_icon()` 行為維持 |
| `installer/make_app_icon.py` | **新增**生成腳本：用同一支 `app_pixmap()` 繪製 16/24/32/48/64/128/256，逐格編碼 PNG，寫成 `installer\WSL Deck.ico`（標準 ICO 容器） |
| `WSL Deck.spec` | `EXE()` 增加 `icon="installer/WSL Deck.ico"` |
| `build.ps1` | 在呼叫 PyInstaller 前先執行 `installer\make_app_icon.py`，確保每次打包的 exe 圖標都與 `app_icon.py` 同步 |
| `installer/WSL Deck.iss` | `[Icons]` 兩個捷徑條目顯式加 `IconFilename: "{app}\{#MyAppExeName}"`、`IconIndex: 0`，意圖明確不依賴隱含預設 |

- 圖標只有一份來源：`app/ui/app_icon.py`，生成腳本只是把同一份繪製結果落成 `.ico`，未來改 App 圖標只需重跑 `build.ps1`。
- 不動安裝程式本身（Setup.exe）的圖標，不動 App 視窗圖標外觀，不動任何 UI 樣式。
- 多尺寸 ICO 以 PNG 壓縮儲存（Vista+ 支援）；PyInstaller 會原樣嵌入為 RT_ICON 資源。

## 3. 驗證

1. `.\.venv\Scripts\python.exe installer\make_app_icon.py` → 產出 `installer\WSL Deck.ico`，並用 QIcon 重新載入該檔，確認 7 個尺寸都存在且非空白。
2. 把 256px 與 32px 轉存 PNG 目視檢查，確認與 App 內圖標同一造型。
3. `.\build.ps1` 重新打包，從 `dist\WSL Deck\WSL Deck.exe` 抽出關聯圖標轉 PNG，確認不再是 PyInstaller 預設圖標。
4. `.\.venv\Scripts\python.exe -m unittest discover -s tests -q`，預期 71 項全過（本次無業務邏輯變更）。
5. 重新執行 `.\build-installer.ps1` 產出 Setup（是否實際安裝到本機由你決定；如已安裝舊版，需覆蓋安裝才會更新捷徑圖標，Windows 圖標快取偶爾需重新整理）。

## 4. 風險與回滾

| 風險 | 對策 |
|------|------|
| 生成腳本在無字型環境下畫出方框 | 生成時使用預設 Windows 平台插件（已實測正常），不強制 offscreen；打包建置僅在本機執行 |
| Windows 對 PNG 壓縮的 ICO 相容性 | 目標最低 Windows 10，完全支援；PyInstaller 6.22.3 逐條目原樣嵌入，已核對其 `icon.py` 實作 |
| 覆蓋安裝後捷徑仍顯示舊圖標 | 因 Windows 圖標快取；必要時重建捷徑或清快取，屬顯示層問題不影響功能 |
| 圖標檔案被 `--clean` 清掉 | `.ico` 屬原始碼資源，放在 `installer\`，`--clean` 只清 `build\`；且每次建置都會重新生成 |

回滾：還原上述 4 個既有檔案並刪除 `installer\make_app_icon.py`、`installer\WSL Deck.ico`（修改前快照與 SHA256 基線會在動工前存入 `_m7-snapshots\<時間戳>\`）。

## 5. 確認清單

- [ ] 同意把 `app_icon.py` 的繪製邏輯抽成 `app_pixmap(size)`，並加入 256px 尺寸。
- [ ] 同意新增 `installer/make_app_icon.py` 生成 `installer\WSL Deck.ico`（單一來源，隨打包自動重生）。
- [ ] 同意 `WSL Deck.spec` 指定 `icon=`，`build.ps1` 建置前先生成圖標。
- [ ] 同意 `WSL Deck.iss` 的兩個捷徑明確指定使用 exe 圖標。
- [ ] 同意不改安裝程式 Setup.exe 自身圖標，也不改任何畫面樣式。

確認後才動工。

## 6. 實作結果（2026-11-04）

- 修改前快照與 SHA256 基線：`_m7-snapshots\20261104-113501`。
- `installer\WSL Deck.ico` 已生成：7 個尺寸（16/24/32/48/64/128/256），全部為 PNG 壓縮幀，造型與 App 內圖標一致。
- `build.ps1` 重新打包成功，PyInstaller 記錄 `Copying icon to EXE`；從 `dist\WSL Deck\WSL Deck.exe` 的資源區讀到 1 組 `RT_GROUP_ICON`（7 個尺寸）與 7 個 `RT_ICON`，內容與 ICO 檔一致。
- `build-installer.ps1` 重新產出 `dist\WSL-Deck-Setup-1.0.0.exe`，`[Icons]` 已明確指定 `IconFilename`。
- 單元測試：`Ran 123 tests ... OK`（測試數已由先前 71 增至 123，全數通過）。
- 補充修正：`build.ps1` 改存成 **UTF-8 with BOM**。PS 5.1 以 ANSI 讀取無 BOM 的 UTF-8 腳本時，新增註解結尾的位元組會吞掉換行導致解析失敗；加 BOM 後解析 0 錯誤。

### 驗收提醒

- 已安裝過舊版的機器需**重新執行 Setup 覆蓋安裝**，才會更新 `%localappdata%\Programs\WSL Deck` 下的 exe 與捷徑圖標。
- 若桌面圖標仍顯示舊圖，屬 Windows 圖標快取；登出再登入或重建捷徑即可。
