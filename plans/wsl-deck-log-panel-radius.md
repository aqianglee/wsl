# 日誌面板圓角與內距調整

> 狀態：**已完成**（與詳情頁重組方案一起執行）

## 1. 目標

日誌展示區（`QPlainTextEdit#logView`）：
1. 左上、右上圓角（底部保持直角，與 BottomBar 銜接）。
2. 內容 padding 上下左右 16px（目前文字貼邊）。

## 2. 已核實事實

- [main_window.py](file:///d:/workspaces/workspace-wsl-deck/wsl-deck/wsl-deck/app/ui/main_window.py) `LOG_PANEL_STYLE`（L181-L186）：
  ```css
  QPlainTextEdit#logView {
      background: palette(base);
      border: none;
  }
  ```
  無圓角、無 padding；容器 margins 為 `(24, 8, 24, 0)`。
- 日誌區下方直接接 BottomBar，因此只圓上兩角合理；圓角半徑與表格卡片（10px）一致。

## 3. 變更範圍

| 檔案 | 變更 |
|------|------|
| `app/ui/main_window.py` | `QPlainTextEdit#logView` 增加 `border-top-left-radius: 10px; border-top-right-radius: 10px; padding: 16px;`。 |

只動 QSS，不動結構。

## 4. 驗證

1. `py_compile app\ui\main_window.py`。
2. `unittest discover`（154 項）。
3. 離屏截圖（展開日誌）：上兩角圓弧可見、文字距邊 16px、下緣仍與 BottomBar 貼齊。

## 5. 確認清單

- [ ] 圓角半徑 10px（與表格卡片一致），只圓上兩角。
- [ ] padding 16px 四邊。

確認後動工。
