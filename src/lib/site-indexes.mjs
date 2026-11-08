import fs from "node:fs";
const read = (name) =>
  JSON.parse(
    fs.readFileSync(
      `${process.cwd()}/.cache/site-generated/${name}.json`,
      "utf8",
    ),
  );
export const search = read("search");
export const downloads = read("downloads");
export const budget = read("budget");
export const fileDownload = (path) =>
  downloads.files.find((file) => file.url === "/data/" + path);

export const specimens = read("specimens");

export const nim = read("nim");
