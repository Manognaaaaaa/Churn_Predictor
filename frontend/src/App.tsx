import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useMetrics } from "./api";
import { Header } from "./components/Header";
import type { Screen } from "./components/Header";
import { Intro, introAlreadySeen, markIntroSeen } from "./components/Intro";
import { ProfileModal } from "./components/ProfileModal";
import { SearchPanel } from "./components/SearchPanel";
import { Skeleton } from "./components/bits";
import { useReducedMotion } from "./hooks/useReducedMotion";
import { AppProvider, useApp } from "./state/app";
import Home from "./pages/Home";
import Customers from "./pages/Customers";
import Budget from "./pages/Budget";

const Model = lazy(() => import("./pages/Model"));

function Toast() {
  const { toastState } = useApp();
  if (!toastState) return null;
  return <div key={toastState.key} className="toast" role="status">{toastState.msg}</div>;
}

function Shell() {
  const reduced = useReducedMotion();
  const metrics = useMetrics();
  const { profileId } = useApp();
  const [screen, setScreen] = useState<Screen>("home");
  const [intro, setIntro] = useState(() => !introAlreadySeen());
  const [introKey, setIntroKey] = useState(0);
  const [searchOpen, setSearchOpen] = useState(false);

  const endIntro = useCallback(() => { markIntroSeen(); setIntro(false); }, []);
  const replay = useCallback(() => { setIntro(false); window.setTimeout(() => { setIntroKey((k) => k + 1); setIntro(true); }, 50); }, []);

  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setSearchOpen(true); }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, []);

  const go = (s: Screen) => { setScreen(s); window.scrollTo({ top: 0 }); };

  return (
    <div style={{ position: "relative", minHeight: "100vh" }}>
      {intro && !reduced && <Intro key={introKey} onDone={endIntro} />}
      <Header screen={screen} onScreen={go} trainedAt={metrics.data?.trained_at} onSearch={() => setSearchOpen(true)} onReplay={replay} />
      <main aria-hidden={profileId ? true : undefined}>
        <AnimatePresence mode="wait">
          <motion.div
            key={screen}
            initial={reduced ? false : { opacity: 0, y: 16, filter: "blur(4px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={reduced ? { opacity: 0 } : { opacity: 0, y: -8 }}
            transition={{ duration: reduced ? 0 : 0.6, ease: [0.22, 1, 0.36, 1] }}
          >
            {screen === "home" && <Home onBudget={() => go("budget")} />}
            {screen === "customers" && <Customers />}
            {screen === "budget" && <Budget />}
            {screen === "model" && (
              <Suspense fallback={<div style={{ padding: "56px clamp(16px, 3.4vw, 48px)" }}><Skeleton w={420} h={44} /></div>}>
                <Model />
              </Suspense>
            )}
          </motion.div>
        </AnimatePresence>
      </main>
      <SearchPanel open={searchOpen} onClose={() => setSearchOpen(false)} />
      <ProfileModal />
      <Toast />
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  );
}
