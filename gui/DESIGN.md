# 🪟 AutoDubStudio — Fluent UI v9 Design System

**Основа:** [Microsoft Fluent UI React v9](https://github.com/microsoft/fluentui)
**Версия:** `@fluentui/react-components` ^9.74.1
**Стек:** Tauri v2 + React 19 + TypeScript + Vite 7
**Цель:** Точная копия Windows 11 — 0% кастомного UI/UX кода

---

## 🔗 Референсы

| Ресурс | Статус | Описание |
|--------|--------|----------|
| [microsoft/fluentui](https://github.com/microsoft/fluentui) | ✅ **Основа** | Официальный репозиторий. Storybook, документация, исходный код |
| [Fluent UI Storybook](https://storybooks.fluentui.dev/react) | ✅ **Доки** | 1087 сниппетов, все компоненты с примерами |
| [Fluent Theme Designer](https://storybooks.fluentui.dev/react?path=/docs/theme-theme-designer--docs) | ✅ **Темы** | Генератор 16-цветного rampa для бренда |
| rasskull/fluent-ui-react-v9 | ❌ **Мимо** | Figma-интеграция, не UI-референс |
| lepoco/wpfui | ❌ **Мимо** | WPF/C# библиотека, не наш стек |
| shindodkar/windows-11-os-clone | ❌ **Мимо** | Tailwind-клон Windows 11 в браузере |

---

## 🧠 Философия

```
100% Fluent UI v9. 0% кастомного UI/UX.
Каждый пиксель, каждый цвет, каждый отступ — из Fluent.
```

### Принципы:
1. **FluentProvider** — корень всего. `webDarkTheme` / `webLightTheme`.
2. **Design Tokens** — никаких хардкод-цветов. `tokens.colorBrandForeground1`, только так.
3. **typographyStyles** — весь текст через Fluent-токены, не через font-size в инлайнах.
4. **Griffel makeStyles** — если нужен кастомный стиль, только через `makeStyles` с Fluent-токенами.
5. **Fluent-иконки** — `@fluentui/react-icons` с `bundleIcon` для filled/regular вариантов.
6. **Никакого кастомного CSS** за исключением того, что Fluent физически не предоставляет.

---

## 🎨 Темизация

### Базовые темы

```tsx
import { FluentProvider, webDarkTheme, webLightTheme } from '@fluentui/react-components';

// Авто-определение: тёмные темы → webDarkTheme, светлые → webLightTheme
const isDark = ['dim', 'night', 'dark', 'dracula', 'abyss', 'black', 'nord'].includes(theme);
<FluentProvider theme={isDark ? webDarkTheme : webLightTheme}>
  <App />
</FluentProvider>
```

### Бренд-токены (кастомизация)

```tsx
import { tokens } from '@fluentui/react-components';

// Для кастомного бренд-цвета (Teknorob indigo):
const customBrand: PartialTheme = {
  colorBrandForeground1: '#4f46e5',
  colorBrandBackground: '#4f46e5',
  colorBrandBackground2: '#eef2ff',
  colorBrandStroke1: '#4f46e533',
};
```

### Поддерживаемые темы (13)

`light`, `dark`, `dim`, `night`, `nord`, `dracula`, `sunset`, `forest`, `abyss`, `silk`, `business`, `caramellatte`, `black`

Все темы работают через `data-theme` атрибут и инвертируют FluentProvider между `webLightTheme` и `webDarkTheme`.

---

## 📐 Типографика (Fluent Type Ramp)

Все стили текста — через `typographyStyles`:

```tsx
import { makeStyles, typographyStyles } from '@fluentui/react-components';

const useStyles = makeStyles({
  pageTitle: typographyStyles.title2,       // 28/36 Semibold
  sectionTitle: typographyStyles.subtitle1,  // 20/28 Semibold
  body: typographyStyles.body1,              // 14/20 Regular
  caption: typographyStyles.caption1,        // 12/16 Regular
  mono: {
    ...typographyStyles.caption1,
    fontFamily: tokens.fontFamilyMonospace,
  },
});
```

### Type Ramp Reference

| Стиль | Размер/Высота | Вес | Использование |
|-------|--------------|-----|---------------|
| `title1` | 28/36 | Semibold (600) | Заголовки страниц |
| `title2` | 22/28 | Semibold (600) | Заголовки секций |
| `title3` | 20/28 | Semibold (600) | Заголовки карточек |
| `subtitle1` | 20/28 | Semibold (600) | Подзаголовки |
| `subtitle2` | 16/22 | Semibold (600) | Мелкие подзаголовки |
| `body1` | 14/20 | Regular (400) | Основной текст |
| `body1Strong` | 14/20 | Semibold (600) | Жирный текст |
| `body2` | 12/16 | Regular (400) | Вторичный текст |
| `caption1` | 12/16 | Regular (400) | Подписи, метаданные |
| `caption1Strong` | 12/16 | Semibold (600) | Жирные подписи |

### Шрифты

- **Sans:** `Segoe UI Variable` → `Inter` → `system-ui` (Windows 11 system font stack)
- **Mono:** `JetBrains Mono` → `Cascadia Code` → `Consolas` → `monospace`

---

## 🎯 Цветовая система (Fluent 2 Tokens)

### Основные токены

| Токен | Назначение |
|-------|-----------|
| `colorNeutralForeground1` | Основной текст |
| `colorNeutralForeground2` | Вторичный текст |
| `colorNeutralForeground3` | Третичный текст (подписи) |
| `colorNeutralForeground4` | Отключённый текст |
| `colorNeutralBackground1` | Фон страницы |
| `colorNeutralBackground2` | Фон карточек/сайдбара |
| `colorNeutralBackground3` | Фон элементов ввода |
| `colorNeutralStroke1` | Границы акцентные |
| `colorNeutralStroke2` | Границы обычные |
| `colorBrandForeground1` | Акцентный текст |
| `colorBrandBackground` | Акцентный фон (кнопки) |
| `colorBrandBackground2` | Акцентный фон (hover/selected) |
| `colorBrandStroke1` | Акцентная граница |

### Семантические токены

| Токен | Назначение |
|-------|-----------|
| `colorPaletteGreenForeground1` | Успех |
| `colorPaletteGreenBackground2` | Фон успеха |
| `colorPaletteGreenBorder1` | Граница успеха |
| `colorPaletteYellowForeground1` | Предупреждение |
| `colorPaletteYellowBackground2` | Фон предупреждения |
| `colorPaletteYellowBorder1` | Граница предупреждения |
| `colorPaletteRedForeground1` | Ошибка |
| `colorPaletteRedBackground2` | Фон ошибки |
| `colorPaletteRedBorder1` | Граница ошибки |

---

## 🧩 Fluent UI v9 Компоненты (используемые)

### Layout
- **FluentProvider** — корневой провайдер темы
- **Card** / **CardHeader** / **CardFooter** — карточки
- **CardPreview** — превью в карточках
- **Divider** — разделители
- **Overflow** — оверфлоу-меню

### Navigation
- **TabList** / **Tab** / **TabPanel** — вкладки
- **Breadcrumb** / **BreadcrumbItem** — хлебные крошки
- **Menu** / **MenuItem** / **MenuTrigger** — выпадающие меню
- **Tooltip** — подсказки

### Forms
- **Button** (appearance: primary, secondary, subtle, outline, transparent)
- **Input** — текстовые поля
- **Textarea** — многострочный ввод
- **Select** — выпадающие списки
- **Switch** — переключатели
- **Checkbox** — чекбоксы
- **Radio** / **RadioGroup** — радио-кнопки
- **Field** — обёртка с label
- **Label** — текстовая метка
- **ProgressBar** — прогресс-бар

### Feedback
- **Badge** / **CounterBadge** — бейджи
- **Spinner** — спиннер загрузки
- **Toast** (sonner) — уведомления (единственное исключение из Fluent)

### Surfaces
- **Dialog** / **DialogSurface** / **DialogBody** / **DialogTitle** / **DialogActions** — модальные окна
- **Drawer** / **DrawerBody** / **DrawerHeader** — боковые панели
- **Popover** / **PopoverSurface** / **PopoverTrigger** — поповеры

### Content
- **Text** (as: h1, h2, p, span, pre) — типографика через компоненты
- **Avatar** — аватары
- **Image** — изображения
- **Table** / **TableHeader** / **TableBody** / **TableRow** / **TableCell** — таблицы

### Иконки
- **@fluentui/react-icons** — `*Regular`, `*Filled` варианты
- **bundleIcon** — объединение filled + regular для авто-переключения

---

## 📏 Правила использования компонентов

### 1. Кнопки
```tsx
// ✅ Правильно: Fluent UI Button
<Button appearance="primary" size="large" icon={<PlayRegular />}>
  Start Pipeline
</Button>

// ❌ Неправильно: div с onClick, кастомные стили
<div className="my-button" onClick={...}>Click</div>
```

### 2. Поля ввода
```tsx
// ✅ Правильно: Field + Input
<Field label="Target Language">
  <Select value={lang} onChange={...}>
    <option value="ru">Russian</option>
  </Select>
</Field>

// ❌ Неправильно: label + select без Field
<label>Target Language</label>
<select>...</select>
```

### 3. Модальные окна
```tsx
// ✅ Правильно: Dialog + DialogSurface
<Dialog open={isOpen} onOpenChange={...}>
  <DialogSurface>
    <DialogBody>
      <DialogTitle>Confirm</DialogTitle>
      <DialogActions>
        <Button appearance="primary">OK</Button>
        <Button appearance="secondary">Cancel</Button>
      </DialogActions>
    </DialogBody>
  </DialogSurface>
</Dialog>

// ❌ Неправильно: div с position:fixed
<div className="modal-overlay">...</div>
```

### 4. Текст
```tsx
// ✅ Правильно: Fluent Text компонент
<Text as="h1" size={900} weight="semibold">Dubbing Studio</Text>

// ✅ Или typographyStyles через makeStyles
const useStyles = makeStyles({
  title: typographyStyles.title2,
});
<h1 className={styles.title}>Dubbing Studio</h1>

// ❌ Неправильно: инлайн fontSize/fontWeight
<h1 style={{ fontSize: 28, fontWeight: 700 }}>Dubbing Studio</h1>
```

### 5. Иконки
```tsx
// ✅ Правильно: @fluentui/react-icons с fontSize
import { PlayRegular } from '@fluentui/react-icons';
<PlayRegular style={{ fontSize: 20 }} />

// ✅ Для авто-filled: bundleIcon
import { bundleIcon, PlayFilled, PlayRegular } from '@fluentui/react-icons';
const Play = bundleIcon(PlayFilled, PlayRegular);
<Play style={{ fontSize: 20 }} />
```

### 6. Вкладки
```tsx
// ✅ Правильно: TabList + Tab
<TabList selectedValue={currentTab} onTabSelect={...}>
  <Tab value="general">General</Tab>
  <Tab value="models">AI Models</Tab>
  <Tab value="keys">API Keys</Tab>
  <Tab value="about">About</Tab>
</TabList>
```

---

## 🚫 Что НЕ использовать

| Запрещено | Причина |
|-----------|---------|
| Инлайн-стили `style={{}}` для цветов/шрифтов | Использовать Fluent-токены и typographyStyles |
| DaisyUI классы (`btn`, `card`, `badge`...) | Удалены из проекта |
| Tailwind утилиты (`bg-base-100`, `text-sm`...) | Удалены из проекта |
| lucide-react иконки | Заменены на @fluentui/react-icons |
| `<div onClick>` как кнопки | Использовать `<Button>` |
| `<select>` без `<Field>` | Использовать `<Field>` + `<Select>` |
| `<dialog>` напрямую | Использовать `<Dialog>` Fluent UI |
| `fontWeight: 700` | Fluent: максимум 600 (Semibold) |
| `fontStyle: italic` | Fluent: не использует italic |
| `textTransform: uppercase` | Fluent: sentence case |
| `boxShadow` в инлайн-стилях | Использовать Fluent-токены |

---

## 📂 Единственный разрешённый кастомный CSS

Только то, что Fluent UI **физически не предоставляет**:

```css
/* 1. Скроллбары Win11 */
/* 2. Tauri drag region */
/* 3. Skip-to-content (accessibility) */
/* 4. Reduced motion (prefers-reduced-motion) */
/* 5. Кастомные анимации (fadeIn, slideUp, spin) */
/* 6. Раскладка (flex, gap, overflow — пока нет Fluent-аналога) */
```

Весь остальной CSS — удаляется при обнаружении.

---

## 🏗️ Архитектура приложения

```
gui/src/
├── main.tsx              ← FluentProvider(webDarkTheme | webLightTheme)
├── App.tsx               ← Layout: Titlebar + Sidebar + Main + StatusBar
├── index.css             ← Только: скроллбары, drag, a11y, анимации, layout
├── store.ts              ← i18n (249 ключей, 3 языка), useSettings()
├── pages/
│   ├── DubbingStudio.tsx  ← Card, Button, Select, ProgressBar, Field, Badge, Divider
│   ├── LiveSubtitles.tsx  ← Card, Button, Select, Field, Badge
│   ├── AIChat.tsx         ← Button, Select, Textarea, chat-кастомные зоны
│   └── Settings.tsx       ← TabList, Tab, Card, Input, Select, Switch, Dialog
├── components/
│   ├── StatusBar.tsx       ← Status-индикаторы (GPU, VRAM, Ollama)
│   ├── CommandPalette.tsx  ← Нативный <dialog> + Fluent-иконки
│   ├── ModelDownloader.tsx ← Card, Button, прогресс-бары
│   ├── ErrorBoundary.tsx   ← Fluent-иконки, семантические цвета
│   ├── UpdateChecker.tsx   ← Tauri updater, Fluent-иконки
│   └── VirtualLogViewer.tsx← Виртуальный скролл, моноширинный
├── hooks/
│   ├── useOllama.ts
│   ├── useModelStatus.ts
│   ├── usePipelineWebSocket.ts
│   └── useLiveWebSocket.ts
└── lib/
    ├── toast.ts           ← sonner (единственный не-Fluent компонент)
    ├── errorReporter.ts
    └── utils.ts
```

---

## 🎮 Клавиатурные сокращения (Windows 11)

| Сочетание | Действие |
|-----------|----------|
| `Ctrl+1` | Студия Дубляжа |
| `Ctrl+2` | Лайв Субтитры |
| `Ctrl+3` | ИИ Чат |
| `Ctrl+,` | Настройки |
| `Ctrl+K` | Командная палитра |

---

## 🔍 Accessibility (WCAG 2.1 AA)

- `FluentProvider` — встроенный accessible theme
- `role="tab"`, `aria-selected`, `aria-controls` — на всех вкладках
- `aria-label` — на всех иконках-кнопках
- `role="log"`, `aria-live="polite"` — лог-вьювер
- `skip-to-content` — ссылка для клавиатурной навигации
- `prefers-reduced-motion` — уважение системных настроек
- Focus ring — через Fluent UI (кастомный `:focus-visible`)

---

## 📦 Зависимости

```json
{
  "@fluentui/react-components": "^9.74.1",
  "@fluentui/react-icons": "^2.0.330",
  "@tauri-apps/api": "^2",
  "@tauri-apps/plugin-dialog": "^2.7.1",
  "@tauri-apps/plugin-http": "^2.5.9",
  "@tauri-apps/plugin-opener": "^2",
  "@tauri-apps/plugin-process": "^2.3.1",
  "@tauri-apps/plugin-shell": "^2.3.5",
  "@tauri-apps/plugin-store": "^2.4.3",
  "@tauri-apps/plugin-updater": "^2.10.1",
  "@tauri-apps/plugin-window-state": "^2.4.1",
  "motion": "^12.40.0",
  "react": "^19.1.0",
  "react-dom": "^19.1.0",
  "react-markdown": "^10.1.0",
  "remark-gfm": "^4.0.1",
  "sonner": "^2.0.7"
}
```

---

## 🚀 Roadmap дизайна

1. ✅ **Phase 1:** Удаление DaisyUI/Tailwind, базовая миграция на Fluent UI v9
2. ✅ **Phase 2:** Замена всех иконок lucide-react → @fluentui/react-icons
3. **Phase 3:** Миграция инлайн-стилей → makeStyles + typographyStyles
4. **Phase 4:** Замена нативных dialog → Dialog Fluent UI
5. **Phase 5:** Полный аудит — удаление всех остатков кастомного CSS

---

*Версия: v8.0 от 2026-06-18*
*Основа: [Microsoft Fluent UI React v9](https://github.com/microsoft/fluentui) · [Storybook](https://storybooks.fluentui.dev/react)*
