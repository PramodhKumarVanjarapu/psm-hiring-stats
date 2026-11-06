import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { Layout } from "./components/Layout";
import { Loading } from "./components/ui";
import { CompaniesPage, CompanyPage } from "./pages/Companies";
import { ConflictsPage } from "./pages/Conflicts";
import { JobPage } from "./pages/Job";
import { JobsPage } from "./pages/Jobs";
import { LoginPage } from "./pages/Login";
import { NewAnalysisPage } from "./pages/NewAnalysis";
import { OverviewPage } from "./pages/Overview";
import { SettingsPage } from "./pages/Settings";
import { StudentPage } from "./pages/Student";
import { StudentsPage } from "./pages/Students";

export function App() {
  const { user, ready, can } = useAuth();
  if (!ready) return <div className="p-8"><Loading /></div>;
  if (!user) return <LoginPage />;
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<OverviewPage />} />
        <Route path="analyses/new" element={can("editor") ? <NewAnalysisPage /> : <Navigate to="/" />} />
        <Route path="analyses/:id" element={<NewAnalysisPage />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="jobs/:jobId" element={<JobPage />} />
        <Route path="companies" element={<CompaniesPage />} />
        <Route path="companies/:name" element={<CompanyPage />} />
        <Route path="students" element={<StudentsPage />} />
        <Route path="students/:id" element={<StudentPage />} />
        <Route path="conflicts" element={<ConflictsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Route>
    </Routes>
  );
}
