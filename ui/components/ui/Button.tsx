import { cn } from "../../utils/cn";
export default function Button({ children, onClick, variant="primary", className="" }: any) {
  const styles = {
    primary: "bg-gradient-to-r from-aqua to-grape text-black hover:opacity-95",
    ghost: "bg-white/5 text-ink hover:bg-white/10",
    warn: "bg-gradient-to-r from-citrus to-punch text-black hover:opacity-95",
  }[variant];
  return (
    <button onClick={onClick} className={cn("px-4 py-2 rounded-xl shadow-glow transition", styles, className)}>
      {children}
    </button>
  );
}
