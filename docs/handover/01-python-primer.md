# 給 Java 底子的 Python 速成

> 目的：不教你「Python 是什麼」，只講**讀懂這個專案所需的差異**。每一條都附本專案真實例子，照著點開看即可。
> 讀完你應該能回答：為什麼 `self` 要寫在參數列？為什麼 `dataclass` 沒有 getter？為什麼 UI 裡看不到 `new Thread()`？

---

## 1. 先給結論：八個心智模型要改的地方

| # | Java 的直覺 | Python／本專案的做法 |
|---|------------|-------------------|
| 1 | 編譯期檢查型別 | 執行期才檢查；型別註解只是給人和工具看，**不會**阻止錯誤 |
| 2 | 一切都是類與介面 | 模組（檔案）就是組織單位；介面用「約定 + `Protocol`」表達 |
| 3 | `new` 建立物件 | 直接呼叫類別：`Config(path)` |
| 4 | getter／setter 樣板 | `@property` 直接寫在類別裡，外部當欄位用 |
| 5 | checked exception 要宣告 | 沒有 checked exception，全部是執行期異常，靠約定與文件 |
| 6 | `synchronized`／`ExecutorService` | `QThreadPool` + `QRunnable`；GIL 讓 CPU 密集thread 無效，但本專案的thread 都在等子進程 |
| 7 | Maven／Gradle 管依賴 | `venv` + `pip` + `requirements.txt`，沒有傳遞依賴鎖定 |
| 8 | 建置產出 jar | PyInstaller 把整個 Python 直譯器＋程式碼包成資料夾（onedir） |

---

## 2. 語言層對照

### 2.1 模組、套件、import

**Java**：`package com.foo.bar;` + `import com.foo.bar.Baz;`，目錄結構必須對應 package。
**Python**：一個 `.py` 檔就是一個模組，一個有 `__init__.py` 的目錄就是一個套件。`import` 路徑從「專案根」算起。

本專案：[app/\_\_init\_\_.py](../../wsl-deck/app/__init__.py) 與 [app/ui/\_\_init\_\_.py](../../wsl-deck/app/ui/__init__.py) 都是**空檔**，它們的作用只是宣告「這是一個套件」。

```python
# main.py:22
from app.config import Config, ConfigError
```

等價於 Java 的 `import app.config.Config;`。注意本專案**全部使用絕對匯入**，沒有 `from .config import ...` 這種相對匯入——這是刻意統一的風格，讓任何檔案都能被獨立執行與測試。

**與 Java 最大的不同**：`import` 是「執行模組頂層程式碼」而不是「載入類別」。所以頂層不要寫有副作用的程式碼。本專案唯一有副作用的頂層語句是 [logbus.py:15](../../wsl-deck/app/logbus.py#L15) 的全域 `log_bus = LogBus()`（建立一個 Qt 物件），這是它可以被接受的原因：UI 需要一個全域訊號匯流排。

> 實務提醒：`if __name__ == "__main__":`（[main.py:63](../../wsl-deck/main.py#L63)）等價於 Java 的 `public static void main`——只有「直接執行這個檔案」時才會跑。

### 2.2 虛擬環境與依賴（venv 對比 Maven）

| Java | Python（本專案） |
|------|----------------|
| `pom.xml` | [requirements.txt](../../wsl-deck/requirements.txt)：只有一行 `PySide6-Essentials==6.12.0` |
| `mvn dependency:tree` | `pip list` |
| 本地倉庫 `~/.m2` | `.venv/Lib/site-packages` |
| `mvnw` 保證版本 | 沒有 wrapper；靠 `.venv` 目錄本身 |

- `.venv` 是「把 Python 直譯器 + 依賴複製一份到專案內」的概念，啟動方式不是 `source`，而是**直接呼叫裡面的執行檔**：`.\.venv\Scripts\python.exe`、`.\.venv\Scripts\pythonw.exe`。
- 因此本專案所有命令都寫死 `.venv` 路徑，不需要先 `activate`。這對 AI／腳本執行反而更方便。
- `==` 是精確版本鎖；`requirements.txt` 沒有傳遞依賴清單，PySide6-Essentials 自己帶的 Qt 函式庫由 pip 解析。
- 沒有 `pyproject.toml`、沒有 `setup.py`：本專案不是要發布到 PyPI 的套件，只是一個可執行的應用，所以不需要。

### 2.3 型別系統：註解不是合約

```python
# app/config.py:3
from __future__ import annotations
```

這一行讓所有型別註解變成「字串」，好處是可以在註解裡寫 `list[str]`、`X | None` 而不受執行版本限制，也避免循環匯入時的求值問題。

```python
# app/wsl.py:70-74
def run_wsl_process(
    args: list[str],
    timeout: int = 60,
    stdin_text: str | None = None,
) -> tuple[int, str, str]:
```

對照 Java：

```java
public static Tuple3<Integer, String, String> runWslProcess(
    List<String> args, int timeout, String stdinText) { ... }
```

**關鍵差異**：Python 不會因為你傳錯型別而編譯失敗，錯誤要等執行到那一行才爆。本專案的防線是：
- 邊界（外部輸入、`config.json`）做明確校驗：[config.py:251](../../wsl-deck/app/config.py#L251) 的 `_validate()`；
- 內部資料用 `frozen dataclass`（見 2.4），至少欄位名不會拼錯；
- **沒有** mypy／pyright 把關（見第 3.3 節）。

泛型在本專案只用了一處：

```python
# app/snapshot.py:27-28
Stage = Callable[[str], None]
T = TypeVar("T")
```

`TypeVar` 等價於 Java 的 `<T>`；`Stage` 是「型別別名」，等價於 `@FunctionalInterface interface Stage { void run(String msg); }`。

### 2.4 `dataclass` 對比 POJO／Lombok

```python
# app/wsl.py:24-33
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
```

這 10 行等價於 Java 的：

```java
public final class Distro {           // final ← frozen=True
    private final String name;        // final 欄位
    ... 8 個欄位 ...
    // 全參數建構子、equals、hashCode、toString、getter 全自動
}
```

- `@dataclass` 自動生成 `__init__`、`__repr__`、`__eq__`。
- `frozen=True` 讓欄位指派後不可改（像 Java 的 `final`），並且 `__hash__` 可用（可以放進 `set`／當 `dict` key）。
- **沒有 getter**：外部直接寫 `distro.name`，不是 `distro.getName()`。
- 本專案用 `@dataclass` 的地方：[wsl.py:24](../../wsl-deck/app/wsl.py#L24)、[distro_ops.py:24](../../wsl-deck/app/distro_ops.py#L24)、[distro_settings.py:31](../../wsl-deck/app/distro_settings.py#L31)、[snapshot.py:73](../../wsl-deck/app/snapshot.py#L73)、[network.py:19](../../wsl-deck/app/network.py#L19)、[workspace.py:19](../../wsl-deck/app/workspace.py#L19)、[proxy.py:26](../../wsl-deck/app/proxy.py#L26)、[admin.py:18](../../wsl-deck/app/admin.py#L18)。
- 可變的那一個：[network.py:26](../../wsl-deck/app/network.py#L26) 的 `ApplyResult` 沒有 frozen，因為它要在流程中持續 `append` errors／warnings。

### 2.5 `@property`、dunder、`self`

```python
# app/wsl.py:35-43
@property
def size_gb(self) -> float:
    return self.vhdx_size / 1024 ** 3

@property
def running(self) -> bool:
    if "running" in self.state.lower():
        return True
    return any(word in self.state for word in ("运行中", "執行中", "运行", "執行"))
```

`@property` 等價於 Java 的 `getSizeGb()`，但**外部寫 `distro.size_gb`**，不帶括號。好處是呼叫端看不出它是算出來的；代價是不能傳參數。

`self` 等價於 Java 的 `this`，但**必須明寫在參數列第一項**，因為 Python 不會隱式注入。`__init__` 等價於建構子。

`__xxx__`（dunder）是 Python 的「協定方法」，等價於 Java 的 `equals`／`hashCode`／`toString` 這類有固定語意的特殊方法。本專案直接用到的不多：`__init__`（[config.py:94](../../wsl-deck/app/config.py#L94)）、`__name__`（[main.py:63](../../wsl-deck/main.py#L63)）。

### 2.6 異常

```python
# app/config.py:74-75
class ConfigError(Exception):
    """配置檔內容不合法。"""
```

等價於 Java 的 `class ConfigError extends Exception {}`。本專案只有三個自訂異常：

| 異常 | 定義 | 語意 |
|------|------|------|
| `ConfigError` | [config.py:74](../../wsl-deck/app/config.py#L74) | 設定檔格式／型別／範圍不合法 |
| `WslError` | [wsl.py:20](../../wsl-deck/app/wsl.py#L20) | `wsl.exe` 找不到、逾時、非零退出碼 |
| （其餘用內建 `ValueError`／`RuntimeError`／`OSError`） | — | 參數不合法／環境問題 |

**沒有 checked exception**：方法不必宣告 `throws`。本專案的補償方式是「在邊界集中處理」：

```python
# app/config.py:105-108
try:
    self.data = json.loads(self.path.read_text(encoding="utf-8"))
except json.JSONDecodeError as exc:
    raise ConfigError(f"配置檔格式錯誤：{exc}") from exc
```

`raise ... from exc` 等價於 Java 的 `throw new ConfigError(msg, cause)`，會保留原始堆疊。

再看一個「刻意吞掉」的例子：

```python
# app/ui/workers.py:44-50
try:
    result = self.fn(*self.args, **self.kwargs)
except Exception as exc:  # noqa: BLE001 - 錯誤需回報到 UI
    logger.exception("背景工作失敗")
    self._emit(self.signals.failed, str(exc))
```

`except Exception` 等價於 `catch (Exception e)`。這裡吞掉是**正確的**：背景工作不能讓例外逃到執行緒池，必須轉成訊號回報 UI。`# noqa: BLE001` 是給 linter 的抑制註解（本專案其實沒有跑 linter，這是習慣留下來的）。

> 讀程式時看到 `except Exception` 先問一句：它有沒有把錯誤**傳出去**（訊號、回傳值、日誌）？沒有才是 bug。

### 2.7 `with`：一定會關的資源

```python
# app/wsl.py:139-166
with root:
    ...
    with winreg.OpenKey(root, guid) as key:
        name = _query_value(key, "DistributionName")
```

```python
# app/network.py:140-145
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    try:
        sock.bind(("0.0.0.0", port))
```

等價於 Java 的 try-with-resources。自訂類別要支援 `with` 得實作 `__enter__`／`__exit__`，本專案沒有自訂的，全部是標準庫／Qt 物件。

### 2.8 推導式與生成器運算式

| 寫法 | 等價 Java | 本專案例子 |
|------|----------|-----------|
| `[x for x in xs if cond]` | `stream().filter().collect()` | [config.py:227-231](../../wsl-deck/app/config.py#L227-L231) |
| `{k: v for ...}` | `Collectors.toMap` | [proxy.py:64](../../wsl-deck/app/proxy.py#L64) |
| `{x for ...}` | `Collectors.toSet` | [network.py:207](../../wsl-deck/app/network.py#L207) |
| `any(...)`／`all(...)` | `anyMatch`／`allMatch` | [wsl.py:43](../../wsl-deck/app/wsl.py#L43)、[snapshot.py:410](../../wsl-deck/app/snapshot.py#L410) |
| `next(gen, None)` | `findFirst().orElse(null)` | [main_window.py:356-362](../../wsl-deck/app/ui/main_window.py#L356-L362) |

`any(...)`／`all(...)` 吃的是「生成器」，**短路求值**，不會先建出整個 list。這是 Python 慣用的效能寫法。

```python
# app/ui/main_window.py:356-362
default = next(
    (
        item for item in distros
        if item.is_default and not self._is_system(item.name)
    ),
    None,
)
```

讀法：在 `distros` 裡找第一個「是預設且不是系統實例」的元素，找不到就 `None`。

### 2.9 lambda 與閉包：**延遲綁定**的坑

Java 的 lambda 捕捉的是「有效 final 的值」；Python 的 lambda 捕捉的是**變數名**，在呼叫時才求值。

```python
# app/ui/view_toggle.py:51-64
for mode, icon, tooltip in (
    ("card", grid_icon(), "卡片視圖"),
    ("list", list_icon(), "表格視圖"),
):
    ...
    button.clicked.connect(
        lambda _checked=False, value=mode: self._on_clicked(value)
    )
```

`value=mode` 是**刻意的預設參數**：把當下的 `mode` 值「凍結」進 lambda。如果寫成 `lambda: self._on_clicked(mode)`，兩個按鈕都會拿到最後一個 `mode`（`"list"`）——這是 Python 最經典的迴圈閉包陷阱。

同樣的模式在 [main_window.py:344](../../wsl-deck/app/ui/main_window.py#L344)：

```python
system_check = lambda name: is_system_distro(name, system_prefixes)
```

這裡沒有迴圈，所以不需要凍結。

另一個常用工具是 `functools.partial`，等價於 Java 的「先綁定部分參數再當回呼」：

```python
# app/ui/main_window.py:556-557
worker.signals.finished.connect(partial(self._on_task_finished, worker, on_done))
worker.signals.failed.connect(partial(self._on_task_failed, worker, on_error))
```

### 2.10 真假值：`if not x` 不是 `x == false`

Python 的 falsy 值包含：`None`、`False`、`0`、`0.0`、`""`、`[]`、`{}`、`set()`。

```python
# app/config.py:119-131
workspace = str(self.data.get("workspace_root") or "").strip()
if workspace:
    return workspace
```

`or ""` 的意思是「若左邊是 falsy 就用右邊」——等價於 Java 的 `Objects.toString(x, "")` 再加 trim。這招在本專案用得很多：

```python
# app/distro_ops.py:97
stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
```

**陷阱**：`if port:` 在 `port=0` 時會是 False。所以本專案在驗證端口時一律寫 `isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65535`（[config.py:347](../../wsl-deck/app/config.py#L347)）——因為 Python 的 `bool` 是 `int` 的子類，`True` 會被當成 `1` 通過範圍檢查。這是 Java 沒有的坑。

### 2.11 可變與不可變、預設參數

Python 的函式預設參數**只求值一次**，所以 `def f(items=[])` 會讓所有呼叫共用同一個 list。本專案沒有這個寫法（本次已用 grep 確認），但你要新增函式時別踩。

本專案的替代做法是 `None` + 函式內建立：

```python
# app/network.py:150
def build_admin_job(
    targets: list[tuple[str, str, list[dict]]],
    cleanup: list[tuple[str, int]] | None = None,
) -> dict:
```

`None` 表示「沒給」，函式內再用 `cleanup or []`。

### 2.12 命名慣例

| 前綴／形式 | 含義 | 例子 |
|-----------|------|------|
| `_name` | 模組內部使用（**約定**，不是編譯期限制） | `_clean_output`、`_with_proxy`、`_stage` |
| `__name` | 名稱改寫（name mangling），本專案沒用 | — |
| `UPPER_CASE` | 模組級常數 | `DEFAULT_CONFIG`、`RESTIC_VERSION` |
| `PascalCase` | 類別 | `TaskWorker`、`Distro` |
| `snake_case` | 函式、變數、模組檔名 | `run_wsl_process`、`main_window.py` |

Java 的 `getFoo()` 在 Python 是 `foo`（property）或 `get_foo()`（必要時）。

### 2.13 GIL 與執行緒

CPython 有全域解譯器鎖（GIL）：同一時間只有一個執行緒在跑 Python 位元組碼。因此「多執行緒加速 CPU 計算」在 Python 基本無效。

但**本專案的背景工作都在等子進程**（`subprocess.run` 等待 `wsl.exe`、`netsh`、restic）。等待期間會釋放 GIL，所以 `QThreadPool` 仍然是有效的：

```python
# app/ui/workers.py:32-60
class TaskWorker(QRunnable):
    def run(self) -> None:
        ...
        result = self.fn(*self.args, **self.kwargs)
```

等價於 Java：

```java
executor.submit(() -> { ...; return result; });
```

> 若你之後要加「大量純計算」的功能（例如壓縮、雜湊），要考慮 `multiprocessing` 或丟給外部程式，而不是再開 thread。

---

## 3. 工程工具鏈

### 3.1 unittest 對 JUnit

| JUnit 5 | unittest（本專案） |
|---------|------------------|
| `@Test` | 方法名以 `test_` 開頭 |
| `@BeforeEach` | `setUp(self)` |
| `@AfterEach` | `tearDown(self)` |
| `@BeforeAll` | `setUpClass(cls)` |
| `assertEquals` | `assertEqual` |
| `assertThrows` | `with self.assertRaises(...)` |
| 測試類別 | `class XxxTest(unittest.TestCase)` |

本專案沒有用 pytest，全部是標準庫 `unittest`：

```python
# tests/test_config.py:13-20
class ConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "config.json"
        self.config = Config(self.path)

    def tearDown(self) -> None:
        self._tmp.cleanup()
```

執行方式（**不是** `pytest`）：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

### 3.2 mock：不打真實外部依賴

```python
# tests/test_distro_settings.py:123
with patch("app.distro_settings.subprocess.run", return_value=proc):
```

`patch("模組.屬性")` 等價於 Mockito 的 `mockStatic`／注入 mock。**必須 patch「使用它的地方」**，不是 patch 來源（例如 patch `app.distro_settings.subprocess.run`，而不是 `subprocess.run`）——這是 Python mock 最常犯的錯。

`TemporaryDirectory` 等價於 JUnit 的 `@TempDir`，用 `with` 保證清理。

### 3.3 本專案**沒有**的基建（要有心理準備）

| 缺失 | 後果 |
|------|------|
| 沒有 lint（ruff／flake8、沒有設定檔） | 風格全靠人工維持；`# noqa` 註解是形式上的 |
| 沒有型別檢查（mypy／pyright） | 型別註解不會被驗證，重構時容易漏改 |
| 沒有格式化工具（black／ruff format） | 缩排與引號風格靠作者自律 |
| 沒有 CI | 測試只在你手動跑時才跑 |
| 沒有 coverage | 135 項測試集中在「純函式」與「解析邏輯」，UI 幾乎沒測 |
| 沒有依賴鎖（`requirements.txt` 只鎖一層） | 換機器重裝可能拿到不同的傳遞依賴 |

> 這不是「Python 生態就這樣」，而是**這個專案沒做**。你要補的話，成本很低：`pip install ruff mypy`，加一個 `pyproject.toml` 即可。

### 3.4 PyInstaller

等價於 Java 的 `jpackage`／GraalVM native-image，但原理不同：它把**整個 Python 直譯器**＋標準庫＋你的程式碼＋Qt DLL 全部複製到 `dist\WSL Deck\`，產生一個 `WSL Deck.exe` 啟動器。

- 本專案用 **onedir**（一個資料夾），不是 onefile（單檔自解壓）。onedir 啟動快、除錯容易、可看到 `_internal`。
- `hiddenimports=["app.admin"]` 見 [03-build-release.md](./03-build-release.md#3-pyinstaller-onedir)：因為 `app.admin` 只在 `--admin-job` 分支被動態匯入，PyInstaller 靜態分析看不到。

---

## 4. 讀這個 repo 的實用技巧

### 4.1 用「型別 + 函式名」當導航

Python 沒有 IDE 的「Find Usages」那麼可靠，但有兩個替代：

```powershell
# 找某個符號被誰用（PowerShell + Select-String；或直接用編輯器的全局搜尋）
Select-String -Path app\*.py,app\ui\*.py -Pattern "run_wsl_process"
```

```powershell
# 找某個類別的所有方法
Select-String -Path app\ui\main_window.py -Pattern "^    def "
```

### 4.2 用 REPL 驗證小片段

不必寫測試檔，直接互動執行：

```powershell
.\.venv\Scripts\python.exe -c "from app.config import split_command; print(split_command('wsl.exe -d \"my distro\" -- true'))"
```

### 4.3 縮排就是語法

Python 用縮排表達區塊，**混用 Tab 與空白會直接 `IndentationError`**。本專案全部是 4 個空白。設定你的編輯器「Tab 轉 4 spaces」，並且開啟「顯示空白字元」。

### 4.4 檔案編碼

本專案所有 `.py` 都是 UTF-8（註解與字串含中文）。`config.json` 讀寫時明確指定 `encoding="utf-8"`（[config.py:106](../../wsl-deck/app/config.py#L106)、[config.py:180](../../wsl-deck/app/config.py#L180)）——**不要**依賴系統預設編碼，Windows 的預設是 cp950／cp936。

---

## 5. Qt 心智模型

### 5.1 QApplication 與事件迴圈 ≈ Swing 的 EDT

```python
# main.py:30
app = QApplication([sys.argv[0], *argv])
...
# main.py:60
return app.exec()
```

`app.exec()` 啟動事件迴圈，之後**所有 UI 操作都只能在主執行緒發生**（跟 Swing 的 EDT 一樣）。你在背景執行緒直接改 widget，會隨機崩潰或畫面錯亂——這就是為什麼本專案所有 UI 更新都透過訊號排回主執行緒。

### 5.2 Widget 樹與記憶體：parent 就是 owner

```python
# app/ui/card_wall.py:72
card = InstanceCard(distro, system_check(distro.name), self)   # 第三個參數是 parent
```

Qt 的物件有父子關係：**父物件被銷毀時會自動銷毀子物件**。這解決了 Java 要靠 GC、而 native 資源（視窗、畫筆）不能靠 GC 的問題。

- 傳 `self` 當 parent，等於「交給這個容器管理生命週期」。
- 動態移除時要顯式處理：`card.setParent(None); card.deleteLater()`（[card_wall.py:65-67](../../wsl-deck/app/ui/card_wall.py#L65-L67)），否則它還會留在畫面上。
- `deleteLater()` 等價於「排進事件迴圈，稍後安全刪除」，不能在訊號槽裡直接 `del`。

### 5.3 Signal／Slot ≈ 監聽器，但更安全

```python
# app/ui/detail_page.py:24-41
class DetailPage(QWidget):
    back_requested = Signal()
    start_requested = Signal(str)
    ...
```

等價於 Java：

```java
public interface DetailPage {
    void addBackListener(Runnable l);
    void addStartListener(Consumer<String> l);
}
```

但差別在於：

1. **型別安全**：`Signal(str)` 只能接 `(str) -> None` 的槽，接錯會在執行期警告。
2. **可跨執行緒**：訊號從背景執行緒發出，槽會自動排到接收者所在執行緒（見 5.4）。
3. **多對多**：一個訊號可以接多個槽，不需要自己維護 listener list。

**本專案的單向資料流**：子元件只發訊號，不直接呼叫 `MainWindow`。所以 `DetailPage` 完全不知道 `MainWindow` 存在——這是 UI 層唯一做對的解耦。

### 5.4 QRunnable／QThreadPool ≈ ExecutorService

```python
# app/ui/workers.py:32-60
class TaskWorker(QRunnable):
    def __init__(self, fn: Callable, *args, with_stage: bool = False, **kwargs):
        ...
        self.signals = TaskSignals()

    def run(self) -> None:
        result = self.fn(*self.args, **self.kwargs)
        self._emit(self.signals.finished, result)
```

```python
# app/ui/main_window.py:553-558
worker = TaskWorker(fn, *args, **kwargs)
worker.signals.finished.connect(partial(self._on_task_finished, worker, on_done))
QThreadPool.globalInstance().start(worker)
```

對照 Java：

```java
Future<?> f = executor.submit(() -> {
    try { T r = fn.get(); onDone.accept(r); }
    catch (Exception e) { onError.accept(e.getMessage()); }
});
```

**與 ExecutorService 的三個差異**：

| 差異 | 說明 |
|------|------|
| 沒有 `Future` | 結果靠訊號回呼，不靠 `get()` 阻塞 |
| 執行緒池是全域的 | `QThreadPool.globalInstance()`，沒有自訂 pool 大小 |
| 例外必須自己接 | `run()` 裡沒接住的例外會被 Qt 印到 stderr 然後消失 |

本專案的 `_workers` 集合（[main_window.py:92](../../wsl-deck/app/ui/main_window.py#L92)）只是為了**防止 worker 被 GC 回收**（Python 物件沒有參考就會消失，跟 Java 不同），不是執行緒管理。

### 5.5 QSS 與 `palette()`

```python
# app/ui/instance_card.py:60-68
self.setStyleSheet(
    """
    QFrame#instanceCard {
        background: palette(base);
        border: 1px solid palette(mid);
        border-radius: 10px;
    }
    """
)
```

QSS ≈ CSS，但選擇器是 Qt 的 objectName（`#instanceCard` 對應 `setObjectName("instanceCard")`）。`palette(base)`／`palette(mid)` 是**Qt 的調色盤角色**，會隨 [`theme.py`](../../wsl-deck/app/ui/theme.py) 設定的深／淺色 palette 自動變化。

> 因此：**不要在 QSS 裡寫死顏色**（除了強調色 `#2D7FF9` 這類刻意固定的）。寫死會讓深色主題出現白底黑字。

主題切換只有兩步（[theme.py:47-55](../../wsl-deck/app/ui/theme.py#L47-L55)）：`app.setStyle("Fusion")` + `app.setPalette(...)`。沒有換 QSS 檔案，所以自訂樣式必須靠 `palette()` 才能跟著變。

### 5.6 模態對話框與巢狀事件迴圈

```python
# app/ui/main_window.py:671-692
def _run_operation(self, title, fn, on_success, on_error=None) -> None:
    self._timer.stop()
    dialog = OperationDialog(title, self)
    worker = TaskWorker(fn, with_stage=True)
    ...
    QThreadPool.globalInstance().start(worker)
    dialog.exec()          # ← 這裡會阻塞，但會跑一個巢狀事件迴圈
```

`dialog.exec()` 不是 `Thread.sleep`：它會開一個新的事件迴圈，所以進度條會動、視窗會重繪、訊號槽照常執行。等 `accept()`／`reject()` 被呼叫才返回。

**這代表**：`_run_operation()` 之後的程式碼（重啟計時器、判斷結果）是在對話框關閉後才跑的。寫這種流程時要想清楚「誰負責關對話框」。

### 5.7 佈局管理 ≈ LayoutManager

| Qt | Java |
|----|------|
| `QVBoxLayout`／`QHBoxLayout` | `BoxLayout` |
| `QGridLayout` | `GridBagLayout`（但簡單得多） |
| `addStretch(1)` | `Box.createGlue()` |
| `setContentsMargins` | `setBorder` + `EmptyBorder` |
| `setSizePolicy(Expanding, Fixed)` | `setMaximumSize` + `preferredSize` |

本專案沒有用絕對定位（除了主視窗右下角的設定浮動按鈕，因為它要覆蓋在 `QStackedWidget` 之上，見 [main_window.py:327-332](../../wsl-deck/app/ui/main_window.py#L327-L332)）。

---

## 6. 讀程式時最容易誤讀的十個地方

| 你會以為 | 實際 |
|---------|------|
| `if not x` 等於 `x == false` | 空字串、`0`、空 list 都是「假」 |
| `x or default` 是三元運算 | 是「取第一個真值」；`0` 會被換掉 |
| `except Exception` 一定是壞事 | 在 worker 邊界是必要的，重點是有沒有回報 |
| `@property` 是欄位 | 是方法，只是呼叫時不用括號 |
| `frozen=True` 讓物件完全不可變 | 只擋欄位重新指派；欄位若指向 list，list 內容仍可改 |
| `import` 只載入定義 | 會執行模組頂層程式碼（含副作用） |
| 背景執行緒可以直接更新 UI | 不行，必須用訊號排回主執行緒 |
| `TaskWorker` 被 GC 也無所謂 | 會被回收，所以 `_workers` 要留參考 |
| `dialog.exec()` 會凍住程式 | 它會跑巢狀事件迴圈，UI 仍可運作 |
| 型別註解會在執行期檢查 | 不會，純粹給人與工具看 |

---

## 7. 下一步

- 想知道「模組之間怎麼串」→ [02-architecture.md](./02-architecture.md)
- 想動手改東西 → 先讀 [05-risks-conventions.md](./05-risks-conventions.md) 的破壞性操作與編碼約定
- 想打包 → [03-build-release.md](./03-build-release.md)
