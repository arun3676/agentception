import * as Select from "@radix-ui/react-select";
import { ChevronDownIcon } from "@radix-ui/react-icons";

export default function AppSelect({ value, onValueChange, options }:{value:string, onValueChange:(v:string)=>void, options:string[]}) {
  return (
    <Select.Root value={value} onValueChange={onValueChange}>
      <Select.Trigger className="bg-panel/80 border border-white/5 rounded-xl px-3 py-2 text-left w-full flex items-center justify-between focus:outline-none focus:ring-2 focus:ring-white/10">
        <Select.Value placeholder="Select a role..." />
        <Select.Icon>
          <ChevronDownIcon className="h-4 w-4 text-sub" />
        </Select.Icon>
      </Select.Trigger>
      <Select.Portal>
        <Select.Content className="bg-panel border border-white/10 rounded-xl shadow-soft z-50 min-w-[200px]">
          <Select.ScrollUpButton className="flex items-center justify-center h-6 bg-panel text-sub">
            <ChevronDownIcon className="h-4 w-4 rotate-180" />
          </Select.ScrollUpButton>
          <Select.Viewport className="p-1">
            {options.map((option)=>(
              <Select.Item 
                key={option} 
                value={option} 
                className="px-3 py-2 rounded-lg hover:bg-white/5 cursor-pointer focus:outline-none focus:bg-white/5 text-sm"
              >
                <Select.ItemText>{option}</Select.ItemText>
              </Select.Item>
            ))}
          </Select.Viewport>
          <Select.ScrollDownButton className="flex items-center justify-center h-6 bg-panel text-sub">
            <ChevronDownIcon className="h-4 w-4" />
          </Select.ScrollDownButton>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
}
