export default function Spinner({ label, className }: { label?: string, className?: string }) {
  return (
    <div className={`flex items-center gap-3 text-sub ${className}`}>
      <div className="h-4 w-4 rounded-full border-2 border-white/20 border-t-white/70 animate-spin" />
      {label && <span>{label}</span>}
    </div>
  );
}
