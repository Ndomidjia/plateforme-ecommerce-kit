import { createContext, useContext, useEffect, useState } from "react";
import { api } from "../api";

const AuthContext = createContext(null);

function decodeJwt(token) {
  // Lecture des claims côté client (username/role) pour l'affichage — la
  // vérification cryptographique du jeton se fait côté API à chaque appel,
  // ce décodage ne sert qu'à l'UI (pas une validation de sécurité).
  const payload = token.split(".")[1];
  const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(atob(base64));
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("token"));
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem("token");
    return saved ? { username: decodeJwt(saved).sub, role: decodeJwt(saved).role } : null;
  });

  useEffect(() => {
    if (token) localStorage.setItem("token", token);
    else localStorage.removeItem("token");
  }, [token]);

  async function login(username, password) {
    const { access_token } = await api.login(username, password);
    setToken(access_token);
    const claims = decodeJwt(access_token);
    setUser({ username: claims.sub, role: claims.role });
  }

  function logout() {
    setToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ token, user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
