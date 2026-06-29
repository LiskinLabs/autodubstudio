import type { Meta, StoryObj } from "@storybook/react-vite";
import { Button, Tooltip } from "@fluentui/react-components";
import {
  MoviesAndTvRegular as Film,
  MicRegular as Mic,
  ChatRegular as Chat,
  SearchRegular as Search,
  WeatherMoonRegular as Moon,
} from "@fluentui/react-icons";

/** Fluent UI Button — все варианты из AutoDubStudio */
const meta: Meta<typeof Button> = {
  title: "🧩 Fluent UI/Button",
  component: Button,
  tags: ["autodocs"],
  argTypes: {
    appearance: {
      control: "select",
      options: ["primary", "secondary", "subtle", "outline", "transparent"],
    },
    size: { control: "select", options: ["small", "medium", "large"] },
    shape: { control: "select", options: ["rounded", "circular", "square"] },
    disabled: { control: "boolean" },
  },
};

export default meta;
type Story = StoryObj<typeof Button>;

// ── Variants ──
export const Primary: Story = { args: { appearance: "primary", size: "large", children: "Start Pipeline" } };
export const Secondary: Story = { args: { appearance: "secondary", size: "large", children: "Settings" } };
export const Subtle: Story = { args: { appearance: "subtle", size: "medium", children: "Cancel" } };
export const Transparent: Story = { args: { appearance: "transparent", size: "small", children: "Menu" } };
export const Outline: Story = { args: { appearance: "outline", size: "medium", children: "Browse Files" } };

// ── With Icons (like App.tsx) ──
export const WithIcon: Story = {
  args: { appearance: "primary", size: "large", icon: <Film style={{ fontSize: 20 }} />, children: "Dubbing Studio" },
};

// ── Icon-Only (circular, like titlebar buttons) ──
export const IconOnly: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 8 }}>
      <Tooltip content="Search commands" relationship="label">
        <Button appearance="subtle" size="small" shape="circular" icon={<Search style={{ fontSize: 16 }} />} />
      </Tooltip>
      <Tooltip content="Toggle theme" relationship="label">
        <Button appearance="subtle" size="small" shape="circular" icon={<Moon style={{ fontSize: 16 }} />} />
      </Tooltip>
    </div>
  ),
};

// ── Sidebar Nav (like the Win11 Settings nav) ──
export const SidebarNav: Story = {
  render: () => {
    const items = [
      { id: "dubbing", icon: <Film style={{ fontSize: 20 }} />, label: "Dubbing Studio", active: true },
      { id: "live", icon: <Mic style={{ fontSize: 20 }} />, label: "Live Subtitles", active: false },
      { id: "chat", icon: <Chat style={{ fontSize: 20 }} />, label: "AI Chat", active: false },
    ];
    return (
      <div style={{ display: "flex", flexDirection: "column", width: 260, gap: 4 }}>
        {items.map((item) => (
          <Button
            key={item.id}
            appearance={item.active ? "secondary" : "subtle"}
            icon={item.icon}
            style={{
              justifyContent: "flex-start",
              fontWeight: item.active ? 600 : 400,
            }}
          >
            {item.label}
          </Button>
        ))}
      </div>
    );
  },
};

// ── All Appearances Grid ──
export const AllAppearances: Story = {
  render: () => (
    <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
      {(["primary", "secondary", "subtle", "outline", "transparent"] as const).map((a) => (
        <div key={a} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {(["small", "medium", "large"] as const).map((s) => (
            <Button key={`${a}-${s}`} appearance={a} size={s}>
              {a} {s}
            </Button>
          ))}
        </div>
      ))}
    </div>
  ),
};
