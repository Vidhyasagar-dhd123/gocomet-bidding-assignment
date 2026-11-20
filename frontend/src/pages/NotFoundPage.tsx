import { Link } from "react-router-dom";
import { Notice } from "@/components/ui";

export function Component() {
  return <Notice action={<Link to="/auctions">Go to auctions</Link>}>This page does not exist.</Notice>;
}
