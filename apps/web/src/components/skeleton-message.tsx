"use client";

export function SkeletonMessage() {
  return (
    <article className="message assistant skeleton" aria-busy="true" aria-label="Подготавливаю ответ">
      <div className="skelLine skelLine--lg" />
      <div className="skelCard">
        <div className="skelHeader" />
        <div className="skelTableRow" />
        <div className="skelTableRow" />
        <div className="skelTableRow" />
      </div>
      <div className="skelCard">
        <div className="skelHeader" />
        <div className="skelChart" />
      </div>
    </article>
  );
}
