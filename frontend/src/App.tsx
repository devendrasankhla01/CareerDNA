import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { useAuth } from "./lib/auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Readiness from "./pages/student/Readiness";
import Passport from "./pages/student/Passport";
import Career from "./pages/student/Career";
import PathToReady from "./pages/student/PathToReady";
import Companies from "./pages/student/Companies";
import PlacementJourney from "./pages/student/Placement";
import Queue from "./pages/faculty/Queue";
import QueueDetail from "./pages/faculty/QueueDetail";
import Overview from "./pages/tpo/Overview";
import Skills from "./pages/tpo/Skills";
import Interventions from "./pages/tpo/Interventions";
import ImportPage from "./pages/tpo/ImportPage";
import TpoDepartments from "./pages/tpo/Departments";
import TpoCompanies from "./pages/tpo/Companies";
import TpoDrives from "./pages/tpo/Drives";
import TpoMatching from "./pages/tpo/Matching";
import VerificationCenter from "./pages/tpo/VerificationCenter";
import TpoPlacements from "./pages/tpo/Placements";
import DeptOverview from "./pages/dept/Overview";
import DeptSkills from "./pages/dept/Skills";
import DeptPerformance from "./pages/dept/Performance";
import DeptCompanies from "./pages/dept/Companies";
import DeptPlacements from "./pages/dept/Placements";
import DeptDataUpdates from "./pages/dept/DataUpdates";
import CompanyOverview from "./pages/company/Overview";
import CompanyDrives from "./pages/company/Drives";
import CompanySelections from "./pages/company/Selections";
import ModelPage from "./pages/ModelPage";

function HomeRedirect() {
  const { user } = useAuth();
  return <Navigate to={user ? homeFor(user.role) : "/login"} replace />;
}

function LegacyFacultyRedirect() {
  const { id } = useParams();
  return <Navigate to={`/verifier/queue/${id}`} replace />;
}

function Protected({ role, children }: { role?: string; children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role) return <Navigate to={homeFor(user.role)} replace />;
  return <>{children}</>;
}

export function homeFor(role: string) {
  if (role === "STUDENT") return "/student";
  if (role === "FACULTY" || role === "VERIFIER") return "/verifier/queue";
  if (role === "DEPARTMENT") return "/department";
  if (role === "COMPANY") return "/company";
  return "/tpo";
}

export default function App() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/login" element={user ? <Navigate to={homeFor(user.role)} replace /> : <Login />} />
      <Route element={<Layout />}>
        {/* student */}
        <Route path="/student" element={<Protected role="STUDENT"><Readiness /></Protected>} />
        <Route path="/student/passport" element={<Protected role="STUDENT"><Passport /></Protected>} />
        <Route path="/student/career" element={<Protected role="STUDENT"><Career /></Protected>} />
        <Route path="/student/path" element={<Protected role="STUDENT"><PathToReady /></Protected>} />
        <Route path="/student/companies" element={<Protected role="STUDENT"><Companies /></Protected>} />
        <Route path="/student/placement" element={<Protected role="STUDENT"><PlacementJourney /></Protected>} />
        {/* verifier (lightweight faculty verification, TPO-assigned) */}
        <Route path="/verifier/queue" element={<Protected role="FACULTY"><Queue /></Protected>} />
        <Route path="/verifier/queue/:id" element={<Protected role="FACULTY"><QueueDetail /></Protected>} />
        {/* TPO */}
        <Route path="/tpo" element={<Protected role="TPO_ADMIN"><Overview /></Protected>} />
        <Route path="/tpo/skills" element={<Protected role="TPO_ADMIN"><Skills /></Protected>} />
        <Route path="/tpo/interventions" element={<Protected role="TPO_ADMIN"><Interventions /></Protected>} />
        <Route path="/tpo/import" element={<Protected role="TPO_ADMIN"><ImportPage /></Protected>} />
        <Route path="/tpo/departments" element={<Protected role="TPO_ADMIN"><TpoDepartments /></Protected>} />
        <Route path="/tpo/companies" element={<Protected role="TPO_ADMIN"><TpoCompanies /></Protected>} />
        <Route path="/tpo/drives" element={<Protected role="TPO_ADMIN"><TpoDrives /></Protected>} />
        <Route path="/tpo/matching" element={<Protected role="TPO_ADMIN"><TpoMatching /></Protected>} />
        <Route path="/tpo/verification" element={<Protected role="TPO_ADMIN"><VerificationCenter /></Protected>} />
        <Route path="/tpo/placements" element={<Protected role="TPO_ADMIN"><TpoPlacements /></Protected>} />
        {/* department */}
        <Route path="/department" element={<Protected role="DEPARTMENT"><DeptOverview /></Protected>} />
        <Route path="/department/skills" element={<Protected role="DEPARTMENT"><DeptSkills /></Protected>} />
        <Route path="/department/performance" element={<Protected role="DEPARTMENT"><DeptPerformance /></Protected>} />
        <Route path="/department/companies" element={<Protected role="DEPARTMENT"><DeptCompanies /></Protected>} />
        <Route path="/department/placements" element={<Protected role="DEPARTMENT"><DeptPlacements /></Protected>} />
        <Route path="/department/data" element={<Protected role="DEPARTMENT"><DeptDataUpdates /></Protected>} />
        {/* company */}
        <Route path="/company" element={<Protected role="COMPANY"><CompanyOverview /></Protected>} />
        <Route path="/company/drives" element={<Protected role="COMPANY"><CompanyDrives /></Protected>} />
        <Route path="/company/selections" element={<Protected role="COMPANY"><CompanySelections /></Protected>} />
        <Route path="/model" element={<Protected><ModelPage /></Protected>} />
        {/* legacy faculty paths -> verifier */}
        <Route path="/faculty/queue" element={<Navigate to="/verifier/queue" replace />} />
        <Route path="/faculty/queue/:id" element={<LegacyFacultyRedirect />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
