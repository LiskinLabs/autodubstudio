import{j as e}from"./iframe-CzKZ5Kul.js";import{c as m,B as r,T as g,M as y,C as h}from"./Button-DLpgaZAk.js";import"./preload-helper-PPVm8Dsz.js";import"./index-D78V9wqI.js";const b=m("SearchRegular","1em",["M13.73 14.44a6.5 6.5 0 1 1 .7-.7l3.42 3.4a.5.5 0 0 1-.63.77l-.07-.06-3.42-3.41Zm-.71-.71A5.54 5.54 0 0 0 15 9.5a5.5 5.5 0 1 0-1.98 4.23Z"]),S=m("MicRegular","1em",["M10 13a3 3 0 0 0 3-3V5a3 3 0 1 0-6 0v5a3 3 0 0 0 3 3Zm0-1a2 2 0 0 1-2-2V5a2 2 0 1 1 4 0v5a2 2 0 0 1-2 2ZM5 9.5c.28 0 .5.22.5.5a4.5 4.5 0 1 0 9 0 .5.5 0 0 1 1 0 5.5 5.5 0 0 1-5 5.48v2.02a.5.5 0 0 1-1 0v-2.02a5.5 5.5 0 0 1-5-5.48c0-.28.22-.5.5-.5Z"]),f=m("WeatherMoonRegular","1em",["M15.5 13.5A6.98 6.98 0 0 1 4 14.39c2.83-1.09 4.56-2.42 5.6-4.4 1.04-2 1.33-4.16.75-6.9A6.98 6.98 0 0 1 15.5 13.5ZM5.45 16.92A7.98 7.98 0 1 0 9.88 2.04a.6.6 0 0 0-.61.73c.69 2.82.43 4.88-.55 6.76-.94 1.78-2.55 3.03-5.55 4.1a.6.6 0 0 0-.3.9 7.95 7.95 0 0 0 2.59 2.39Z"]),M={title:"🧩 Fluent UI/Button",component:r,tags:["autodocs"],argTypes:{appearance:{control:"select",options:["primary","secondary","subtle","outline","transparent"]},size:{control:"select",options:["small","medium","large"]},shape:{control:"select",options:["rounded","circular","square"]},disabled:{control:"boolean"}},parameters:{docs:{description:{component:"Fluent UI Button — все варианты из AutoDubStudio"}}}},s={args:{appearance:"primary",size:"large",children:"Start Pipeline"}},t={args:{appearance:"secondary",size:"large",children:"Settings"}},i={args:{appearance:"subtle",size:"medium",children:"Cancel"}},o={args:{appearance:"transparent",size:"small",children:"Menu"}},l={args:{appearance:"outline",size:"medium",children:"Browse Files"}},c={args:{appearance:"primary",size:"large",icon:e.jsx(y,{style:{fontSize:20}}),children:"Dubbing Studio"}},p={render:()=>e.jsxs("div",{style:{display:"flex",gap:8},children:[e.jsx(g,{content:"Search commands",relationship:"label",children:e.jsx(r,{appearance:"subtle",size:"small",shape:"circular",icon:e.jsx(b,{style:{fontSize:16}})})}),e.jsx(g,{content:"Toggle theme",relationship:"label",children:e.jsx(r,{appearance:"subtle",size:"small",shape:"circular",icon:e.jsx(f,{style:{fontSize:16}})})})]})},d={render:()=>{const n=[{id:"dubbing",icon:e.jsx(y,{style:{fontSize:20}}),label:"Dubbing Studio",active:!0},{id:"live",icon:e.jsx(S,{style:{fontSize:20}}),label:"Live Subtitles",active:!1},{id:"chat",icon:e.jsx(h,{style:{fontSize:20}}),label:"AI Chat",active:!1}];return e.jsx("div",{style:{display:"flex",flexDirection:"column",width:260,gap:4},children:n.map(a=>e.jsx(r,{appearance:a.active?"secondary":"subtle",icon:a.icon,style:{justifyContent:"flex-start",fontWeight:a.active?600:400},children:a.label},a.id))})}},u={render:()=>e.jsx("div",{style:{display:"flex",gap:12,flexWrap:"wrap"},children:["primary","secondary","subtle","outline","transparent"].map(n=>e.jsx("div",{style:{display:"flex",flexDirection:"column",gap:8},children:["small","medium","large"].map(a=>e.jsxs(r,{appearance:n,size:a,children:[n," ",a]},`${n}-${a}`))},n))})};s.parameters={...s.parameters,docs:{...s.parameters?.docs,source:{originalSource:`{
  args: {
    appearance: "primary",
    size: "large",
    children: "Start Pipeline"
  }
}`,...s.parameters?.docs?.source}}};t.parameters={...t.parameters,docs:{...t.parameters?.docs,source:{originalSource:`{
  args: {
    appearance: "secondary",
    size: "large",
    children: "Settings"
  }
}`,...t.parameters?.docs?.source}}};i.parameters={...i.parameters,docs:{...i.parameters?.docs,source:{originalSource:`{
  args: {
    appearance: "subtle",
    size: "medium",
    children: "Cancel"
  }
}`,...i.parameters?.docs?.source}}};o.parameters={...o.parameters,docs:{...o.parameters?.docs,source:{originalSource:`{
  args: {
    appearance: "transparent",
    size: "small",
    children: "Menu"
  }
}`,...o.parameters?.docs?.source}}};l.parameters={...l.parameters,docs:{...l.parameters?.docs,source:{originalSource:`{
  args: {
    appearance: "outline",
    size: "medium",
    children: "Browse Files"
  }
}`,...l.parameters?.docs?.source}}};c.parameters={...c.parameters,docs:{...c.parameters?.docs,source:{originalSource:`{
  args: {
    appearance: "primary",
    size: "large",
    icon: <Film style={{
      fontSize: 20
    }} />,
    children: "Dubbing Studio"
  }
}`,...c.parameters?.docs?.source}}};p.parameters={...p.parameters,docs:{...p.parameters?.docs,source:{originalSource:`{
  render: () => <div style={{
    display: "flex",
    gap: 8
  }}>\r
      <Tooltip content="Search commands" relationship="label">\r
        <Button appearance="subtle" size="small" shape="circular" icon={<Search style={{
        fontSize: 16
      }} />} />\r
      </Tooltip>\r
      <Tooltip content="Toggle theme" relationship="label">\r
        <Button appearance="subtle" size="small" shape="circular" icon={<Moon style={{
        fontSize: 16
      }} />} />\r
      </Tooltip>\r
    </div>
}`,...p.parameters?.docs?.source}}};d.parameters={...d.parameters,docs:{...d.parameters?.docs,source:{originalSource:`{
  render: () => {
    const items = [{
      id: "dubbing",
      icon: <Film style={{
        fontSize: 20
      }} />,
      label: "Dubbing Studio",
      active: true
    }, {
      id: "live",
      icon: <Mic style={{
        fontSize: 20
      }} />,
      label: "Live Subtitles",
      active: false
    }, {
      id: "chat",
      icon: <Chat style={{
        fontSize: 20
      }} />,
      label: "AI Chat",
      active: false
    }];
    return <div style={{
      display: "flex",
      flexDirection: "column",
      width: 260,
      gap: 4
    }}>\r
        {items.map(item => <Button key={item.id} appearance={item.active ? "secondary" : "subtle"} icon={item.icon} style={{
        justifyContent: "flex-start",
        fontWeight: item.active ? 600 : 400
      }}>\r
            {item.label}\r
          </Button>)}\r
      </div>;
  }
}`,...d.parameters?.docs?.source}}};u.parameters={...u.parameters,docs:{...u.parameters?.docs,source:{originalSource:`{
  render: () => <div style={{
    display: "flex",
    gap: 12,
    flexWrap: "wrap"
  }}>\r
      {(["primary", "secondary", "subtle", "outline", "transparent"] as const).map(a => <div key={a} style={{
      display: "flex",
      flexDirection: "column",
      gap: 8
    }}>\r
          {(["small", "medium", "large"] as const).map(s => <Button key={\`\${a}-\${s}\`} appearance={a} size={s}>\r
              {a} {s}\r
            </Button>)}\r
        </div>)}\r
    </div>
}`,...u.parameters?.docs?.source}}};const A=["Primary","Secondary","Subtle","Transparent","Outline","WithIcon","IconOnly","SidebarNav","AllAppearances"];export{u as AllAppearances,p as IconOnly,l as Outline,s as Primary,t as Secondary,d as SidebarNav,i as Subtle,o as Transparent,c as WithIcon,A as __namedExportsOrder,M as default};
