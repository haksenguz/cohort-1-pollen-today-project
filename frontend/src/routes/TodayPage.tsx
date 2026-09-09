/**
 * Placeholder for the "Today" (risk + environment) screen. The real view —
 * wired to GET /api/environment/current — is TASKS.md's I6, a separate
 * lane item. This route exists so the shell's nav and layout are complete.
 */
export function TodayPage() {
  return (
    <>
      <h2 className="vt">Today</h2>
      <p className="vsub">Pollen, air quality and your risk score for today.</p>
      <div className="note">
        <span>This screen is built in I6 (risk + hospital screens). The shell and API client are ready for it.</span>
      </div>
    </>
  );
}
