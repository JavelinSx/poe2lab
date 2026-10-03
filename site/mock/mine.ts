// The signed-in author's builds as the cabinet sees them (/api/me/builds): their state and numbers.
export interface MyBuild {
  id: string; title: string; icon: string; state: "published" | "hidden"; patch: string; old?: boolean; when: string;
  views: number; rating?: number; reviews: number; opens: number; newReviews: number;
  description: string; tags: string[]; cover: string;
}

export const MY_BUILDS: MyBuild[] = [
  { id: "b7", title: "Шквал бури: молнии с посоха", icon: "tempest-flurry", state: "published", patch: "0.5.5", when: "обновлён из poe2lab 12 сентября",
    views: 9840, rating: 4.7, reviews: 45, opens: 1920, newReviews: 3, tags: ["маппинг", "старт лиги"], cover: "i-staff2",
    description: "Бьём [[skill:tempest-flurry]] с боевого посоха: каждый третий удар бьёт молнией по области.\nДо 30 уровня играй через [[skill:glacial-cascade]]." },
  { id: "m2", title: "Заряженный посох: заряды для новичков", icon: "charged-staff", state: "published", patch: "0.5.5", when: "обновлён 2 сентября",
    views: 4120, rating: 4.4, reviews: 14, opens: 860, newReviews: 2, tags: ["новичкам"], cover: "i-staff", description: "" },
  { id: "m3", title: "Ледяной каскад хрономанта", icon: "glacial-cascade", state: "published", patch: "0.4.3", old: true, when: "",
    views: 3960, rating: 4.5, reviews: 22, opens: 610, newReviews: 0, tags: ["бюджет"], cover: "i-body3", description: "" },
  { id: "m4", title: "Внезапный удар — черновой", icon: "flicker", state: "hidden", patch: "0.5.5", when: "виден только тебе · снят 30 августа",
    views: 290, reviews: 0, opens: 20, newReviews: 0, tags: [], cover: "i-ring", description: "" },
];
