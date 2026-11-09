function weekday(dateStr) {
  const [y, m, d] = dateStr.split("-").map(Number);
  return new Intl.DateTimeFormat("en-IN", { weekday: "short", timeZone: "UTC" }).format(new Date(Date.UTC(y, m - 1, d)));
}

function dayNumber(dateStr) {
  return Number(dateStr.split("-")[2]);
}

export default function AdherenceBars({ daily }) {
  const peak = Math.max(1, ...daily.map((d) => d.yes + d.no + d.unknown + d.missed));
  const unit = 120 / peak;
  return (
    <div>
      <div className="bars" role="img" aria-label="Daily medicine and reply record for the last two weeks">
        {daily.map((day) => {
          const total = day.yes + day.no + day.unknown + day.missed;
          const label = `${weekday(day.date)} ${dayNumber(day.date)}: ${day.yes} taken, ${day.no} not taken, ${day.unknown} medicine not mentioned, ${day.missed} no reply`;
          return (
            <div key={day.date} className="bar-col" title={label}>
              <div className="bar-well">
                {total === 0 ? (
                  <span className="seg seg-empty" style={{ height: 6 }} />
                ) : (
                  <>
                    {day.missed > 0 && <span className="seg seg-missed" style={{ height: day.missed * unit }} />}
                    {day.unknown > 0 && <span className="seg seg-unknown" style={{ height: day.unknown * unit }} />}
                    {day.no > 0 && <span className="seg seg-no" style={{ height: day.no * unit }} />}
                    {day.yes > 0 && <span className="seg seg-yes" style={{ height: day.yes * unit }} />}
                  </>
                )}
              </div>
              <span className="bar-day">{weekday(day.date)}</span>
              <span className="bar-num">{dayNumber(day.date)}</span>
            </div>
          );
        })}
      </div>
      <ul className="legend">
        <li>
          <span className="swatch seg-yes" /> Medicine taken
        </li>
        <li>
          <span className="swatch seg-no" /> Not taken
        </li>
        <li>
          <span className="swatch seg-unknown" /> Replied, medicine not mentioned
        </li>
        <li>
          <span className="swatch seg-missed" /> No reply
        </li>
      </ul>
    </div>
  );
}
