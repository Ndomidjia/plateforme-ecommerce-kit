import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Nettoie le DOM entre chaque test (sinon des composants de tests
// précédents restent montés et faussent les requêtes getByText suivantes).
afterEach(() => {
  cleanup();
});
