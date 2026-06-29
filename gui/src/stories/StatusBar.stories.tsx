import type { Meta, StoryObj } from "@storybook/react-vite";
import StatusBar from "../components/StatusBar";

/** StatusBar — нижняя панель с GPU/VRAM/моделями */
const meta: Meta<typeof StatusBar> = {
  title: "🪟 AutoDub/StatusBar",
  component: StatusBar,
  tags: ["autodocs"],
  parameters: {
    layout: "fullscreen",
  },
};

export default meta;
type Story = StoryObj<typeof StatusBar>;

export const Default: Story = {
  render: () => (
    <div style={{ position: "fixed", bottom: 0, left: 0, right: 0 }}>
      <StatusBar />
    </div>
  ),
};
