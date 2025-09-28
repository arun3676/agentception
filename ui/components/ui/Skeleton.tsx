export default function Skeleton({ className="" }: any) {
  return <div className={`relative overflow-hidden rounded-xl bg-white/5 ${className}`}>
    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent animate-shimmer bg-[length:200%_100%]" />
  </div>;
}
