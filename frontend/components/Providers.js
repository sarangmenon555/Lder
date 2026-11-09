"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

const TzContext = createContext({ tz: "Asia/Kolkata", setTz: () => {} });

export function Providers({ children }) {
  const [tz, setTzState] = useState("Asia/Kolkata");

  useEffect(() => {
    const saved = window.localStorage.getItem("lder_tz");
    if (saved) {
      setTzState(saved);
      return;
    }
    try {
      const detected = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (detected) setTzState(detected);
    } catch {}
  }, []);

  const setTz = useCallback((value) => {
    setTzState(value);
    window.localStorage.setItem("lder_tz", value);
  }, []);

  return <TzContext.Provider value={{ tz, setTz }}>{children}</TzContext.Provider>;
}

export function useTz() {
  return useContext(TzContext);
}
