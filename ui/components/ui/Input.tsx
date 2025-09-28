export default function Input(props: any) {
  return <input {...props} className={"w-full bg-panel/80 border border-white/5 rounded-xl px-3 py-2 outline-none focus:ring-2 focus:ring-white/10 "+(props.className||"")} />;
}
