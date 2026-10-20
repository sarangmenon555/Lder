"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Shell from "@/components/Shell";
import ElderForm from "@/components/ElderForm";
import { api } from "@/lib/api";

export default function EditElderPage() {
  const { id } = useParams();
  const [elder, setElder] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
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
