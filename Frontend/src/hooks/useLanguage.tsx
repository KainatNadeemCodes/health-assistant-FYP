/**
 * Part of the AI-Powered Smart Health Assistant UI.
 * -------------------------------------------------------------------------
 * Our localization engine. Beyond just translating text, it manages 
 * the "RTL" (Right-to-Left) layout logic required for Urdu. 
 * * It ensures the entire app's direction and language attributes 
 * stay synced with the user's preference across sessions.
 * -------------------------------------------------------------------------
 */

import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

export const useLanguage = () => {
  const { i18n } = useTranslation();
  const [isUrdu, setIsUrdu] = useState(i18n.language === 'ur');

  useEffect(() => {
    const dir = i18n.language === 'ur' ? 'rtl' : 'ltr';
    document.documentElement.dir = dir;
    document.documentElement.lang = i18n.language;
  }, [i18n.language]);

  const toggleLanguage = () => {
    const newLang = isUrdu ? 'en' : 'ur';
    i18n.changeLanguage(newLang);
    localStorage.setItem('language', newLang);
    setIsUrdu(!isUrdu);
  };

  return { isUrdu, toggleLanguage, currentLang: i18n.language };
};
