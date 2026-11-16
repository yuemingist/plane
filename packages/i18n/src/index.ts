/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Components
export { TranslationProvider } from "./provider";

// Hooks
export { useTranslation } from "./hooks/use-translation";
export type { TTranslationStore } from "./hooks/use-translation";

// Types
export type { TLanguage, ILanguageOption } from "./types";
export type { TTranslationKeys } from "./types";
export type { TNamespace } from "./constants/namespaces";

// Utilities
export { setLanguage } from "./core/set-language";
// Non-component translation access (stores/services outside React): raw i18next instance handle
export { getI18n } from "react-i18next";
export { initPromise } from "./core";

// Constants
export { FALLBACK_LANGUAGE, SUPPORTED_LANGUAGES, LANGUAGE_STORAGE_KEY } from "./constants/language";
