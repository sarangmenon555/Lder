"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Shell from "@/components/Shell";
import ElderForm from "@/components/ElderForm";
import { api } from "@/lib/api";

function EditElderView() {
  const id = useSearchParams().get("id");
  const [elder, setElder] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    api.elder(id).then(setElder).catch((err) => setError(err.message));
  }, [id]);

  return (
    <Shell>
      <div className="page-intro">
        <h1>{elder ? `Edit ${elder.name}` : "Edit person"}</h1>
        <p className="lede">Changes apply from the next check-in.</p>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {elder && <ElderForm elder={elder} />}
    </Shell>
  );
}

export default function EditElderPage() {
  return (
    <Suspense fallback={null}>
      <EditElderView />
    </Suspense>
  );
}
