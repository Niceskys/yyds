import type { EventViewModel } from '../contract/viewModel';

interface EventListProps {
  events: EventViewModel[];
  emptyText: string;
}

export function EventList({ events, emptyText }: EventListProps) {
  if (events.length === 0) {
    return <p className="event-list__empty">{emptyText}</p>;
  }
  return (
    <ul className="event-list" data-testid="event-list">
      {events.map((event) => (
        <li
          key={event.id}
          className={event.isUnknown ? 'event event--unknown' : 'event'}
          data-kind={event.kind}
        >
          <span className="event__label">{event.label}</span>
          {event.detail ? <span className="event__detail">{event.detail}</span> : null}
        </li>
      ))}
    </ul>
  );
}
