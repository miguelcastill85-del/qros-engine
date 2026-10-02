export {AuthState,JobState} from './service.mjs';
import {handle} from './service.mjs';
const TEST_NOW=1790950000;
export default {fetch:(req,env)=>handle(req,env,TEST_NOW)};
