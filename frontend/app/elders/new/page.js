"use client";

import Shell from "@/components/Shell";
import ElderForm from "@/components/ElderForm";

export default function NewElderPage() {
  return (
    <Shell>
      <div className="page-intro">
        <h1>Add a person</h1>
        <p className="lede">Four short steps. You can change any of this later.</p>
      </div>
      <ElderForm />
    </Shell>
  );
}
