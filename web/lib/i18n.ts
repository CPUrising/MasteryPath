"use client";

import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from "@/i18n/en.json";
import zh from "@/i18n/zh.json";

if (!i18n.isInitialized) {
  const saved =
    typeof window !== "undefined" ? window.localStorage.getItem("mp.lang") : null;
  void i18n.use(initReactI18next).init({
    resources: { zh: { translation: zh }, en: { translation: en } },
    lng: saved ?? "zh",
    fallbackLng: "zh",
    interpolation: { escapeValue: false },
  });
}

export function setLanguage(lang: "zh" | "en") {
  void i18n.changeLanguage(lang);
  if (typeof window !== "undefined") window.localStorage.setItem("mp.lang", lang);
}

export function currentLanguage(): "zh" | "en" {
  return i18n.language?.toLowerCase().startsWith("en") ? "en" : "zh";
}

export default i18n;
