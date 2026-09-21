import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../api";
import { useAuth } from "../auth/AuthContext";

/** Charge des données via l'API, avec état loading/error et déconnexion
 * automatique si le jeton a expiré (401). `deps` redéclenche le chargement. */
export function useApiQuery(fetcher, deps = []) {
  const { token, logout } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fetcher(token)
      .then(setData)
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          logout();
          navigate("/login");
          return;
        }
        setError(err);
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    reload();
  }, [reload]);

  return { data, error, loading, reload };
}
