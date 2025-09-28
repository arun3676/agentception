import { useEffect, useState } from "react";
export default function TopProgress({ active }: { active: boolean }) {
  const [w, setW] = useState(0);
 useEffect(()=>{ if(!active){ setW(0); return; } let i=0; const id=setInterval(()=>{ i=(i+1)%95; setW(10+i); }, 120); return ()=>clearInterval(id); },[active]);
  return <div className="fixed top-[53px] left-0 right-0 z-20 h-[2px]">
    <div className="h-full bg-gradient-to-r from-aqua via-grape to-citrus transition-all" style={{width: active ? `${w}%` : "0%"}} />
  </div>;
}
