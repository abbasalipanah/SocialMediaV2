import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PlatformDashboard } from "../api";
import { maskCommentMentions } from "../features/dashboard/commentPrivacy";
import { CommunityTables } from "../features/facebook/FacebookPulseDashboard";

describe("comment privacy", () => {
  it("keeps only the first and final character of every standalone mention", () => {
    expect(maskCommentMentions(
      "Hi @_kathistaggl_ @httpx.dilara and @okoeker2254. Mail me@example.com",
    )).toBe("Hi @_***_ @h***a and @o***4. Mail me@example.com");
    expect(maskCommentMentions("@a @ab (@deniz.)")).toBe("@a***a @a***b (@d***z.)");
  });

  it("never renders source usernames and masks mentions in community tables", () => {
    const data = {
      community: {
        top_commenters: [{ name: "visible-user", comments: 7, likes: 2 }],
        top_liked_comments: [{
          name: "another-visible-user",
          comment: "Thanks @visible-user and @_guest_",
          likes: 5,
          replies: 0,
        }],
      },
    } as PlatformDashboard;

    render(<CommunityTables data={data} platform="instagram" />);

    expect(screen.queryByText("visible-user")).not.toBeInTheDocument();
    expect(screen.queryByText("another-visible-user")).not.toBeInTheDocument();
    expect(screen.getAllByText("Anonymous")).toHaveLength(2);
    expect(screen.getByText("Thanks @v***r and @_***_")).toBeInTheDocument();
  });
});
