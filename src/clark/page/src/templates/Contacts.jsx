// Contacts (#96), store type "contacts": its view part. A short list of people to reach: name, role, an email as a mailto: link
// (through the shared check, ./safe.js) and a phone number as text. isEmpty: no person with a name.
// The Edit part is edit/templates/Contacts.jsx; the content rules are section_kinds/contacts.py.
import { source, tidyContacts, contactsEmpty, mailHref } from "./notes.js";

export const READY = true;
export const isEmpty = (section) => contactsEmpty(tidyContacts(source(section)));

export function View({ section }) {
  const c = tidyContacts(source(section));
  return (
    <ul class="tpl-contacts">
      {c.people.map((p, i) => {
        const href = mailHref(p.email);
        return (
          <li class="tpl-contact" key={i}>
            <span class="tpl-contact-name">{p.name}</span>
            {p.role ? <span class="tpl-contact-role">{p.role}</span> : null}
            {p.email ? <span class="tpl-contact-line">{href ? <a href={href}>{p.email}</a> : p.email}</span> : null}
            {p.phone ? <span class="tpl-contact-line">{p.phone}</span> : null}
          </li>
        );
      })}
    </ul>
  );
}
