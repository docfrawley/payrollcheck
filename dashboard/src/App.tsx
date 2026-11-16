import { Navigate, Outlet, Route, Routes } from "react-router";
import { AppearanceChoice } from "./components/AppearanceChoice";
import { ComplianceManagerOnly } from "./components/ComplianceManagerOnly";
import { PageFrame } from "./components/PageFrame";
import { RequireReviewer } from "./components/RequireReviewer";
import { StateMessage } from "./components/StateMessage";
import { SEE_ROUNDS, SEE_SETTINGS } from "./reviewer";
import { CasePage } from "./pages/CasePage";
import { ConfigurationPage } from "./pages/ConfigurationPage";
import { EvaluationPage } from "./pages/EvaluationPage";
import { ImprovementPage } from "./pages/ImprovementPage";
import { ProjectPage } from "./pages/ProjectPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { QueuePage } from "./pages/QueuePage";
import { RecipePage } from "./pages/RecipePage";
import { ScoreboardPage } from "./pages/ScoreboardPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SignInPage } from "./pages/SignInPage";
import { VersionPage } from "./pages/VersionPage";
import {
  CASE_PAGE,
  CONFIGURATION,
  EVALUATION_PAGE,
  IMPROVEMENT,
  INSTRUCTIONS,
  PROJECT_PAGE,
  PROJECTS,
  QUEUE,
  RECIPE_PAGE,
  SCOREBOARD,
  SETTINGS,
  SIGN_IN,
  VERSION_PAGE,
} from "./paths";

export function App() {
  return (
    <Routes>
      <Route path={SIGN_IN} element={<SignInPage />} />
      <Route
        element={
          <RequireReviewer>
            <PageFrame>
              <Outlet />
            </PageFrame>
          </RequireReviewer>
        }
      >
        <Route path={QUEUE} element={<QueuePage />} />
        <Route path={CASE_PAGE} element={<CasePage />} />
        <Route path={PROJECTS} element={<ProjectsPage />} />
        <Route path={PROJECT_PAGE} element={<ProjectPage />} />
        <Route path={SCOREBOARD} element={<ScoreboardPage />} />
        <Route path={EVALUATION_PAGE} element={<EvaluationPage />} />
        <Route
          path={IMPROVEMENT}
          element={
            <ComplianceManagerOnly title="Improvement" action={SEE_ROUNDS}>
              <ImprovementPage />
            </ComplianceManagerOnly>
          }
        />
        <Route
          path={RECIPE_PAGE}
          element={
            <ComplianceManagerOnly title="Recipe" action={SEE_ROUNDS}>
              <RecipePage />
            </ComplianceManagerOnly>
          }
        />
        <Route path={CONFIGURATION} element={<ConfigurationPage />} />
        <Route path={VERSION_PAGE} element={<VersionPage />} />
        <Route
          path={SETTINGS}
          element={
            <ComplianceManagerOnly
              title="Appearance"
              action={SEE_SETTINGS}
              forOthers={<AppearanceChoice />}
            >
              <SettingsPage />
            </ComplianceManagerOnly>
          }
        />
        <Route
          path={INSTRUCTIONS}
          element={<Navigate to={CONFIGURATION} replace />}
        />
        <Route
          path="*"
          element={
            <StateMessage empty="Page not found. Choose a page from the header." />
          }
        />
      </Route>
    </Routes>
  );
}
