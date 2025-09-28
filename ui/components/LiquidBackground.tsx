import { motion } from "framer-motion";
export default function LiquidBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <svg className="absolute inset-0 h-full w-full" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <filter id="goo">
            <feGaussianBlur in="SourceGraphic" stdDeviation="18" result="blur" />
            <feColorMatrix in="blur" mode="matrix"
              values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 20 -10" result="goo" />
            <feBlend in="SourceGraphic" in2="goo" />
          </filter>
          <linearGradient id="g1" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#22d3ee"/>
            <stop offset="100%" stopColor="#a78bfa"/>
          </linearGradient>
          <linearGradient id="g2" x1="1" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#f59e0b"/>
            <stop offset="100%" stopColor="#f43f5e"/>
          </linearGradient>
        </defs>
      </svg>
      <div className="absolute -top-24 left-1/3 h-[32rem] w-[32rem] filter" style={{filter:"url(#goo)"}} />
      <motion.div
        className="absolute -top-24 left-1/3 h-[32rem] w-[32rem] rounded-full blur-3xl"
        style={{ background: "radial-gradient(600px at 200px 200px, #22d3ee33, transparent 60%)" }}
        animate={{ x: [0, 80, -40, 0], y: [0, -50, 30, 0] }}
        transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-[-10rem] right-[-6rem] h-[36rem] w-[36rem] rounded-full blur-3xl"
        style={{ background: "radial-gradient(600px at 200px 200px, #a78bfa33, transparent 60%)" }}
        animate={{ x: [0, -60, 40, 0], y: [0, 60, -30, 0] }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
      />
      <motion.div
        className="absolute top-1/2 left-[-8rem] h-[28rem] w-[28rem] rounded-full blur-3xl"
        style={{ background: "radial-gradient(600px at 200px 200px, #f59e0b33, transparent 60%)" }}
        animate={{ x: [0, 40, 0], y: [0, -40, 0] }}
        transition={{ duration: 20, repeat: Infinity, ease: "easeInOut", delay: 0.2 }}
      />
    </div>
  );
}
