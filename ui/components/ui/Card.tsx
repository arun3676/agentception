import { motion } from "framer-motion";
export default function Card({ title, children, footer }: any) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}
      whileHover={{ y: -2 }}
      className="rounded-2xl bg-panel/80 border border-white/5 shadow-soft"
    >
      {title && <div className="px-4 py-3 border-b border-white/5 text-sub">{title}</div>}
      <div className="p-4">{children}</div>
      {footer && <div className="px-4 py-3 border-t border-white/5">{footer}</div>}
    </motion.div>
  );
}
