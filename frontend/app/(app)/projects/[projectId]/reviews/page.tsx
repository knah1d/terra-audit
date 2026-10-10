"use client";

import { useProjectContext } from "@/components/projects/ProjectContext";
import { ProjectReviewQueue } from "@/components/reviews/ReviewQueue";
import { Card } from "@/components/ui/Card";

/** The project's internal reviews, inside the project workspace. */
export default function ProjectReviewsPage() {
  const project = useProjectContext();
  return (
    <div className="ui-container space-y-6">
      <div>
        <h2 className="ui-section-title">Reviews</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Each field&apos;s calculation is checked by a reviewer before it can go into the MRV report.
          {project.can_manage && " Open a submission to assign its reviewer."}
        </p>
      </div>
      <Card><ProjectReviewQueue projectId={project.project_id} /></Card>
    </div>
  );
}
