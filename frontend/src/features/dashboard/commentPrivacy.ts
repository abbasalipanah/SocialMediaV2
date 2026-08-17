export const ANONYMOUS_COMMENT_AUTHOR = "Anonymous";

// Match standalone @mentions without treating the domain portion of an e-mail
// address as a username. Dots and hyphens may appear inside a username.
const COMMENT_MENTION = /(^|[^\p{L}\p{N}_.%+-])@([\p{L}\p{N}_](?:[\p{L}\p{N}_.-]*[\p{L}\p{N}_])?)/gu;

export function maskCommentMentions(value: string): string {
  return value.replace(COMMENT_MENTION, (_match, prefix: string, username: string) => (
    `${prefix}@${username[0]}***${username.at(-1)}`
  ));
}
