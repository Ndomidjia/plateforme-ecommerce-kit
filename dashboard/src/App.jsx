import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Overview from "./pages/Overview";
import Funnel from "./pages/Funnel";
import Churn from "./pages/Churn";
import Rfm from "./pages/Rfm";
import Recommendations from "./pages/Recommendations";
import AssociationRules from "./pages/AssociationRules";
import Sentiment from "./pages/Sentiment";
import Retention from "./pages/Retention";
import Customer360 from "./pages/Customer360";
import Rgpd from "./pages/Rgpd";
import Admin from "./pages/Admin";
import "./theme.css";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<Overview />} />
            <Route path="/funnel" element={<Funnel />} />
            <Route path="/churn" element={<Churn />} />
            <Route path="/rfm" element={<Rfm />} />
            <Route path="/recommendations" element={<Recommendations />} />
            <Route path="/association-rules" element={<AssociationRules />} />
            <Route path="/sentiment" element={<Sentiment />} />
            <Route path="/retention" element={<Retention />} />
            <Route path="/customer-360" element={<Customer360 />} />

            <Route element={<ProtectedRoute requireRole="admin" />}>
              <Route path="/rgpd" element={<Rgpd />} />
              <Route path="/admin" element={<Admin />} />
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}
